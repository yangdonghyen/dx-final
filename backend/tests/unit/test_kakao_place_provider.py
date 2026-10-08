import json
import socket
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.exceptions import AppError
from app.services.external.place.kakao_provider import KakaoPlaceProvider
from app.services.external.place.region_resolver import RegionResolver, normalize_administrative_name, parse_address_levels, parse_region_levels


def _geojson(path: Path, geometry):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"SIDO_CD": "24"}, "geometry": geometry}]}), encoding="utf-8")


def _document(place_id="inside", x="126.90", y="35.15", address="광주광역시 동구 중앙로"):
    return {"id": place_id, "place_name": "카페", "category_name": "음식점 > 카페", "address_name": address, "x": x, "y": y, "phone": "062-1", "place_url": "https://place.map.kakao.com/1"}


def _provider(resolver, responses):
    calls = []
    def fake(url, headers, timeout):
        calls.append((url, headers, timeout))
        return 200, json.dumps({"documents": responses[len(calls) - 1]}).encode()
    return KakaoPlaceProvider("test-key", 3.5, fake, resolver), calls


def test_maps_kakao_document_to_existing_dto_and_passes_timeout():
    resolver = RegionResolver()
    provider, calls = _provider(resolver, [[_document()]])
    result = provider.search("카페")
    assert result[0].external_provider == "KAKAO" and result[0].external_id == "inside"
    assert (result[0].name, result[0].longitude, result[0].latitude, result[0].phone, result[0].source_url) == ("카페", 126.90, 35.15, "062-1", "https://place.map.kakao.com/1")
    assert "query=%EC%B9%B4%ED%8E%98" in calls[0][0] and calls[0][2] == 3.5 and calls[0][1]["Authorization"] == "KakaoAK test-key"


def test_gwangju_uses_nine_grids_deduplicates_and_filters_administrative_address(tmp_path):
    path = tmp_path / "gwangju.geojson"
    _geojson(path, {"type": "Polygon", "coordinates": [[[126.8, 35.1], [127.0, 35.1], [127.0, 35.2], [126.8, 35.2], [126.8, 35.1]]]})
    resolver = RegionResolver(path)
    responses = [[_document("inside", "126.90", "35.15"), _document("damyang", "127.1", "35.2", "전남광주통합특별시 목포시 관광로")]] + [[_document("inside", "126.90", "35.15")]] * 8
    provider, calls = _provider(resolver, responses)
    result = provider.search("카페", "광주")
    assert [row.external_id for row in result] == ["inside"] and len(calls) == 9 and all("rect=" in url for url, _, _ in calls)
    assert {parse_qs(urlsplit(url).query)["query"][0] for url, _, _ in calls} == {"카페"}


@pytest.mark.parametrize(("region", "kept", "discarded"), [("목포", "목포시", "순천시"), ("순천", "순천시", "목포시"), ("여수", "여수시", "목포시")])
def test_address_policy_regions_send_city_hint_and_filter_only_their_city(region, kept, discarded):
    resolver = RegionResolver()
    provider, calls = _provider(resolver, [[_document("keep", address=f"전남광주통합특별시 {kept} 관광로"), _document("discard", address=f"전남광주통합특별시 {discarded} 관광로")]])
    assert [row.external_id for row in provider.search("카페", region)] == ["keep"]
    assert parse_qs(urlsplit(calls[0][0]).query)["query"] == [f"{region} 카페"]


def test_administrative_helpers_parse_two_levels_and_normalize_suffixes():
    assert parse_address_levels("부산광역시 해운대구 우동") == ("부산광역시", "해운대구")
    assert parse_address_levels("부산광역시") is None
    assert normalize_administrative_name("부산광역시") == "부산"
    assert normalize_administrative_name("목포시") == "목포"
    assert normalize_administrative_name("광산구") == "광산"


def test_region_levels_keep_sido_and_gu_as_separate_normalized_tokens():
    assert parse_region_levels("부산") == ("부산",)
    assert parse_region_levels("부산광역시 수영구") == ("부산", "수영")


@pytest.mark.parametrize(
    ("region", "address", "expected"),
    [
        ("부산", "부산 수영구 광안동 192-20", True),
        ("부산 수영구", "부산 수영구 광안동 192-20", True),
        ("부산광역시 수영구", "부산 수영구 광안동 192-20", True),
        ("부산 수영구", "서울 강남구 역삼동 1", False),
        ("부산 수영구", "부산 해운대구 우동 1", False),
    ],
)
def test_multi_level_region_requires_matching_sido_and_gu(region, address, expected):
    assert RegionResolver().matches_region(address, region) is expected


def test_busan_suyeong_gu_keyword_search_returns_matching_kakao_address():
    resolver = RegionResolver()
    provider, _ = _provider(
        resolver,
        [[_document("gwangalli", address="부산 수영구 광안동 192-20")]],
    )
    result = provider.search("광안리해수욕장", "부산 수영구")
    assert [candidate.external_id for candidate in result] == ["gwangalli"]


def test_busan_query_and_administrative_filter_exclude_other_cities():
    resolver = RegionResolver()
    provider, calls = _provider(resolver, [[
        _document("busan", address="부산광역시 해운대구 우동"),
        _document("seoul", address="서울특별시 중구 명동"),
        _document("gwangju", address="전남광주통합특별시 동구 충장로"),
    ]])
    assert [row.external_id for row in provider.search("맛집", "부산")] == ["busan"]
    assert parse_qs(urlsplit(calls[0][0]).query)["query"] == ["부산 맛집"]


@pytest.mark.parametrize(("region", "kept", "discarded"), [
    ("목포", "전남광주통합특별시 목포시 관광로", "전남광주통합특별시 순천시 관광로"),
    ("순천", "전남광주통합특별시 순천시 관광로", "전남광주통합특별시 목포시 관광로"),
    ("여수", "전남광주통합특별시 여수시 관광로", "전남광주통합특별시 목포시 관광로"),
    ("수원", "경기도 수원시 팔달구", "경기도 성남시 분당구"),
])
def test_administrative_level_filter_handles_general_cities(region, kept, discarded):
    resolver = RegionResolver()
    candidates = [KakaoPlaceProvider._candidate(_document("keep", address=kept)), KakaoPlaceProvider._candidate(_document("discard", address=discarded))]
    assert [row.external_id for row in resolver.filter(candidates, region)] == ["keep"]


def test_gwangju_requires_matching_level1_and_one_of_its_five_gu():
    resolver = RegionResolver()
    accepted = ["동구", "서구", "남구", "북구", "광산구"]
    rejected = [
        "전남광주통합특별시 목포시 관광로",
        "전남광주통합특별시 순천시 관광로",
        "전남광주통합특별시 여수시 관광로",
        "서울특별시 중구 명동",
        "부산광역시 동구 초량동",
    ]
    candidates = [KakaoPlaceProvider._candidate(_document(f"keep-{index}", address=f"전남광주통합특별시 {gu} 충장로")) for index, gu in enumerate(accepted)]
    candidates.extend(KakaoPlaceProvider._candidate(_document(f"discard-{index}", address=address)) for index, address in enumerate(rejected))
    assert [row.external_id for row in resolver.filter(candidates, "광주")] == [f"keep-{index}" for index in range(5)]


@pytest.mark.parametrize("failure,code", [
    (lambda: (401, b"{}"), "KAKAO_AUTH_FAILED"),
    (lambda: (429, b"{}"), "KAKAO_RATE_LIMITED"),
    (lambda: (200, b"not-json"), "KAKAO_MALFORMED_RESPONSE"),
    (lambda: (_ for _ in ()).throw(socket.timeout()), "KAKAO_TIMEOUT"),
    (lambda: (_ for _ in ()).throw(URLError("offline")), "KAKAO_NETWORK_ERROR"),
])
def test_translates_kakao_errors_without_network(failure, code):
    provider = KakaoPlaceProvider("test-key", 1, lambda *_: failure())
    with pytest.raises(AppError) as error: provider.search("카페")
    assert error.value.code == code


def test_missing_key_and_multipolygon_are_handled(tmp_path):
    provider = KakaoPlaceProvider("", 1, lambda *_: pytest.fail("must not call HTTP"))
    with pytest.raises(AppError) as error: provider.search("카페")
    assert error.value.code == "KAKAO_API_KEY_NOT_CONFIGURED"
    path = tmp_path / "multi.geojson"
    _geojson(path, {"type": "MultiPolygon", "coordinates": [[[[126.8, 35.1], [126.9, 35.1], [126.9, 35.2], [126.8, 35.2], [126.8, 35.1]]]]})
    assert RegionResolver(path).in_gwangju(126.85, 35.15)


def test_nearby_category_search_uses_coordinates_radius_and_deduplicates():
    responses = [[_document("nearby", "126.90", "35.15")], [_document("nearby", "126.90", "35.15"), _document("cafe", "126.91", "35.16")]]
    provider, calls = _provider(RegionResolver(), responses)
    result = provider.search_nearby(35.15, 126.90, 5000, ["AT4", "CE7"], 5)
    assert [item.external_id for item in result] == ["nearby", "cafe"]
    query = parse_qs(urlsplit(calls[0][0]).query)
    assert query["x"] == ["126.900000000000"] and query["y"] == ["35.150000000000"]
    assert query["radius"] == ["5000"] and query["sort"] == ["distance"]
