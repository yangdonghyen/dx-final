import json
import socket
from dataclasses import dataclass
from datetime import date

from app.services.cafe_evidence_service import CafeEvidenceService, _branch_tokens, business_match, is_travel_rest_cafe, same_business
import pytest

from app.core.exceptions import AppError
from app.services.external.naver_api_hub_provider import NaverApiHubProvider, NaverBlogPost, NaverLocalPlace


@dataclass
class Place:
    name: str = "해운대 카페"
    address: str = "부산 해운대구 달맞이길 12"
    latitude: float = 35.1580
    longitude: float = 129.1710
    category: str = "CE7"


def test_api_hub_client_uses_search_endpoints_and_headers_without_logging_secrets():
    calls = []
    def fake(url, headers, timeout):
        calls.append((url, headers, timeout))
        payload = {"items": [{"title": "<b>해운대 카페</b>", "category": "카페", "address": "부산 해운대구 달맞이길 12", "roadAddress": "부산 해운대구 달맞이길 12", "mapx": "1291710000", "mapy": "351580000"}]} if "/local" in url else {"items": [{"title": "후기", "description": "요약", "postdate": "20260101", "link": "https://example.test"}]}
        return 200, json.dumps(payload).encode()
    provider = NaverApiHubProvider("search-id", "search-secret", 2, fake)
    local, posts = provider.search_local("해운대 카페"), provider.search_blog("해운대 카페", 2)
    assert (local[0].name, local[0].latitude, local[0].longitude) == ("해운대 카페", 35.158, 129.171)
    assert posts[0].published_on == date(2026, 1, 1)
    assert "/search/v1/local?" in calls[0][0] and "/search/v1/blog?" in calls[1][0]
    assert "format=json" in calls[0][0]
    assert calls[0][1]["X-NCP-APIGW-API-KEY-ID"] == "search-id"
    assert "search-secret" == calls[0][1]["X-NCP-APIGW-API-KEY"]


def test_api_hub_accepts_decimal_and_fixed_point_wgs84_coordinates():
    assert NaverApiHubProvider._coordinate("129.171") == 129.171
    assert NaverApiHubProvider._coordinate("1291710000") == 129.171
    assert NaverApiHubProvider._coordinate("invalid") is None


@pytest.mark.parametrize("failure,code", [
    ((401, b"{}"), "NAVER_API_HUB_AUTH_FAILED"),
    ((500, b"{}"), "NAVER_API_HUB_SERVER_ERROR"),
    ((200, b"not-json"), "NAVER_API_HUB_MALFORMED_RESPONSE"),
    ((200, b'{"items": {}}'), "NAVER_API_HUB_MALFORMED_RESPONSE"),
    (socket.timeout(), "NAVER_API_HUB_TIMEOUT"),
])
def test_api_hub_provider_distinguishes_auth_timeout_server_and_malformed_responses(failure, code):
    def fake(*_):
        if isinstance(failure, BaseException):
            raise failure
        return failure
    with pytest.raises(AppError) as error:
        NaverApiHubProvider("test-id", "test-secret", 1, fake).search_local("카페")
    assert error.value.code == code


def test_business_match_requires_name_address_and_coordinate_and_filters_non_rest_cafes():
    place = Place()
    matched = NaverLocalPlace("해운대 카페", "카페", "부산 해운대구 달맞이길 12", "부산 해운대구 달맞이길 12", 35.1580, 129.1710)
    other_branch = NaverLocalPlace("해운대 카페", "카페", "부산 해운대구 해변로 99", "부산 해운대구 해변로 99", 35.1600, 129.1700)
    assert same_business(place, matched)
    assert not same_business(place, other_branch)
    assert not is_travel_rest_cafe(Place(name="해운대 PC방", category="CE7"))


class EvidenceProvider:
    def __init__(self): self.blog_calls = 0
    def search_local(self, query):
        return [NaverLocalPlace("해운대 카페", "카페", "부산 해운대구 달맞이길 12", "부산 해운대구 달맞이길 12", 35.1580, 129.1710)]
    def search_blog(self, query, limit=5):
        self.blog_calls += 1
        return [
            NaverBlogPost("해운대 카페 방문", "부산 해운대구 달맞이길 조용한 바다 뷰", date(2026, 1, 1), "https://example.test/a"),
            NaverBlogPost("해운대 카페 협찬", "부산 해운대구 달맞이길 광고 방문", date(2026, 1, 1), "https://example.test/b"),
        ]


def test_review_evidence_uses_only_matched_non_ad_visit_text_and_caps_blog_calls():
    provider, place = EvidenceProvider(), Place()
    service = CafeEvidenceService(provider)
    local = service.local_match(place)
    evidence = service.review_evidence(place, local, {"rest_preference": "조용한 휴식 전망"})
    assert evidence.verified and evidence.recent_visit_count == 1
    assert {"VIEW", "QUIET"} <= set(evidence.feature_tags)
    assert service.preference_score(evidence, {"rest_preference": "조용한 휴식 전망"}) == 2


# Phase-1 regression fixtures: ASCII fixtures intentionally avoid Windows
# PowerShell's legacy Korean pipe encoding.  They describe the same structural
# conditions as the production reports (parcel-vs-road, branch suffixes, and
# a capped candidate scan).
@dataclass
class MatchPlace:
    place_id: int
    name: str
    address: str
    latitude: float = 35.1580
    longitude: float = 129.1710
    category: str = "CE7"


def _local(name="Bean Haeundae", address="Busan Haeundae 12", road="Busan Haeundae 12", latitude=35.1580, longitude=129.1710):
    return NaverLocalPlace(name, "Cafe", address, road, latitude, longitude)


def test_phase1_relaxed_same_branch_name_is_a_valid_business_match():
    place = MatchPlace(1, "Bean Haeundae", "Busan Haeundae 12")
    assert same_business(place, _local("Gold Bean Haeundae", "Busan Haeundae 12", "Busan Haeundae 12"))


def test_name_matching_normalizes_whitespace_but_never_uses_address_to_bypass_name():
    place = MatchPlace(1, "On The Hill", "Busan Suyeong-gu 192-5", 35.1541279, 129.1188160)
    assert business_match(place, _local("On  The   Hill", "Busan Suyeong-gu 192-5", "Busan Suyeong-gu 192-5", 35.1541279, 129.1188160)).matched
    different_name = business_match(place, _local("Different Cafe", "Busan Suyeong-gu 192-5", "Busan Suyeong-gu 192-5", 35.1541279, 129.1188160))
    assert (different_name.matched, different_name.reason) == (False, "NAME")


def test_local_match_checks_every_naver_row_and_keeps_other_branch_blocked():
    class Provider:
        def search_local(self, query):
            return [
                _local("Bean CentumBranch", "Busan Haeundae 12", "Busan Haeundae 12", 35.1580, 129.1710),
                _local("Bean HaeundaeBranch", "Busan Haeundae 12", "Busan Haeundae 12", 35.1580, 129.1710),
            ]
        def search_blog(self, query, limit=5):
            return []

    place = MatchPlace(1, "Bean HaeundaeBranch", "Busan Haeundae 12")
    result = CafeEvidenceService(Provider()).local_match_result(place)
    assert result.reason == "MATCHED"
    assert result.local.name == "Bean HaeundaeBranch"


def test_business_match_reports_address_or_distance_after_name_matches():
    place = MatchPlace(1, "Bean Haeundae", "Busan Haeundae 12-3", 35.1580, 129.1710)
    address_failure = business_match(place, _local("Bean Haeundae", "Busan Haeundae 99", "Busan Haeundae 99", 35.1580, 129.1710))
    distance_failure = business_match(place, _local("Bean Haeundae", "Busan Haeundae 12-3", "Busan Haeundae 12-3", 35.1700, 129.1710))
    assert (address_failure.matched, address_failure.reason) == (False, "ADDRESS_DIGITS")
    assert (distance_failure.matched, distance_failure.reason) == (False, "DISTANCE")


def test_phase1_parcel_kakao_address_can_match_naver_parcel_when_road_does_not():
    place = MatchPlace(1, "Bean Haeundae", "Busan Haeundae 12-3")
    assert same_business(place, _local("Bean Haeundae", "Busan Haeundae 12-3", "Busan Haeundae Road 99"))


def test_phase1_different_branches_are_never_joined():
    place = MatchPlace(1, "Bean HarborBranch", "Busan Haeundae 12")
    assert not same_business(place, _local("Bean BeachBranch", "Busan Haeundae 12", "Busan Haeundae 12"))


def test_phase1_containment_does_not_override_an_explicit_korean_branch_token():
    place = MatchPlace(1, "Bean", "Busan Haeundae 12")
    assert not same_business(place, _local("Bean \uD574\uC6B4\uB300\uC810", "Busan Haeundae 12", "Busan Haeundae 12"))


def test_phase1_fourth_candidate_is_reached_within_bounded_local_budget():
    class Provider:
        def __init__(self): self.calls = []
        def search_local(self, query):
            self.calls.append(query)
            name = query.split()[-1]
            return [_local(name if name == "Cafe4" else "Other", "Busan Haeundae 12", "Busan Haeundae 12")]
        def search_blog(self, query, limit=5): return []

    provider = Provider()
    service = CafeEvidenceService(provider)
    places = [MatchPlace(index, f"Cafe{index}", "Busan Haeundae 12") for index in range(1, 11)]
    for place in places[:3]:
        assert service.local_match(place) is None
    assert service.local_match(places[3]) is not None
    assert len(provider.calls) == 4
    assert service.local_lookups <= service.MAX_LOCAL_LOOKUPS


def test_phase1_local_empty_and_no_business_match_have_distinct_result_reasons():
    class Provider:
        def __init__(self, rows): self.rows = rows
        def search_local(self, query): return self.rows
        def search_blog(self, query, limit=5): return []

    place = MatchPlace(1, "Bean Haeundae", "Busan Haeundae 12")
    empty = CafeEvidenceService(Provider([])).local_match_result(place)
    mismatch = CafeEvidenceService(Provider([_local("Other Cafe", "Busan Haeundae 12")])).local_match_result(place)
    assert empty.reason == "NAVER_EMPTY"
    assert mismatch.reason == "NAVER_NO_SAME_BUSINESS"
    assert mismatch.mismatch_condition == "NAME"


def test_phase1_blog_budget_exhaustion_is_not_verified_evidence():
    provider = EvidenceProvider()
    service = CafeEvidenceService(provider)
    places = [MatchPlace(index, f"Cafe{index}", "Busan Haeundae 12") for index in range(1, 4)]
    local = _local("Cafe", "Busan Haeundae 12")
    service.review_evidence(places[0], local, {})
    service.review_evidence(places[1], local, {})
    evidence = service.review_evidence(places[2], local, {})
    assert not evidence.verified


def test_same_business_accepts_independent_address_region_inserted_in_naver_name():
    place = MatchPlace(1, "\uAE08\uC1A1 \uB355\uBBF8 \uD574\uB9AC\uB2E8\uAE38\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    local = _local("\uAE08\uC1A1 \uB355\uBBF8 \uD574\uC6B4\uB300 \uD574\uB9AC\uB2E8\uAE38\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    assert same_business(place, local)


def test_relaxed_containment_keeps_existing_safe_prefix_omission_match():
    place = MatchPlace(1, "Bean Coffee", "Busan Haeundae 12")
    assert same_business(place, _local("Gold Bean Coffee", "Busan Haeundae 12", "Busan Haeundae 12"))


def test_relaxed_containment_rejects_generic_business_name_only():
    place = MatchPlace(1, "\uBCA0\uC774\uCEE4\uB9AC", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    local = _local("\uD6C4\uC2A4\uD6C4\uBB34\uBB34 \uBCA0\uC774\uCEE4\uB9AC", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    assert not same_business(place, local)


def test_branch_tokens_ignore_internal_jeom_and_keep_branch_suffixes():
    assert not _branch_tokens("\uC810\uC2EC\uCE74\uD398 \uC11C\uC810\uCE74\uD398")
    assert _branch_tokens("\uD574\uB9AC\uB2E8\uAE38\uC810 \uB9C8\uB9B0\uC2DC\uD2F0\uC810 \uBCF8\uC810 1\uD638\uC810 \uC5ED\uC810") == {
        "\uD574\uB9AC\uB2E8\uAE38\uC810", "\uB9C8\uB9B0\uC2DC\uD2F0\uC810", "\uBCF8\uC810", "1\uD638\uC810", "\uC5ED\uC810",
    }


def test_nearby_addresses_and_coordinates_do_not_override_different_branch():
    place = MatchPlace(1, "\uAE08\uC1A1 \uB355\uBBF8 \uC13C\uD140\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    local = _local("\uAE08\uC1A1 \uB355\uBBF8 \uD574\uB9AC\uB2E8\uAE38\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    assert not same_business(place, local)


def test_region_removal_does_not_remove_branch_identifier_substring():
    place = MatchPlace(1, "Blue \uD574\uC6B4\uB300\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    local = _local("Blue \uD574\uC6B4\uB300 \uC13C\uD140\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 12")
    assert not same_business(place, local)


def test_rest_slot_budget_reserves_candidates_for_a_second_slot_without_raising_limits():
    class Provider:
        def __init__(self): self.calls = []
        def search_local(self, query):
            self.calls.append(query)
            return [_local("Other", "Busan Haeundae 12", "Busan Haeundae 12")]
        def search_blog(self, query, limit=5): return []

    provider, service = Provider(), CafeEvidenceService(Provider())
    first = [MatchPlace(index, f"First{index}", "Busan Haeundae 12") for index in range(1, 4)]
    service.begin_rest_slot(2)
    for place in first[:2]:
        assert service.local_match_result(place).reason == "NAVER_NO_SAME_BUSINESS"
    assert service.local_match_result(first[2]).reason == "LOCAL_SLOT_BUDGET"
    service.begin_rest_slot(1)
    second = MatchPlace(4, "Second", "Busan Haeundae 12")
    assert service.local_match_result(second).reason == "NAVER_NO_SAME_BUSINESS"
    assert service.local_lookups <= service.MAX_LOCAL_LOOKUPS
    assert len(service._local_candidate_keys) <= service.MAX_LOCAL_CANDIDATES


def test_city_prefix_on_kakao_branch_matches_same_branch_only_within_relaxed_distance():
    place = MatchPlace(1, "\uACF5\uCC28 \uBD80\uC0B0\uD574\uC6B4\uB300\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2")
    local = _local("\uACF5\uCC28 \uD574\uC6B4\uB300\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2", 35.1580216, 129.1710)
    assert same_business(place, local)


@pytest.mark.parametrize("naver_name,latitude,longitude", [
    ("\uACF5\uCC28 \uBD80\uC0B0\uD574\uC6B4\uB300\uAD6C\uCCAD\uC810", 35.1610, 129.1710),
    ("\uACF5\uCC28 NC\uBD80\uC0B0\uD574\uC6B4\uB300\uC810", 35.1750, 129.1710),
    ("\uACF5\uCC28 \uD574\uC6B4\uB300LCT\uC810", 35.1650, 129.1710),
    ("\uACF5\uCC28 \uBD80\uC0B0\uC13C\uD140\uC2DC\uD2F0\uC810", 35.1800, 129.1710),
])
def test_city_prefix_normalization_does_not_join_other_gongcha_branches(naver_name, latitude, longitude):
    place = MatchPlace(1, "\uACF5\uCC28 \uBD80\uC0B0\uD574\uC6B4\uB300\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2")
    local = _local(naver_name, "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC911\uB3D9 1417-2", latitude, longitude)
    assert not same_business(place, local)


def test_naver_only_address_branch_matches_exact_base_name_with_parcel_and_150m_coordinate_check():
    place = MatchPlace(513, "\uC628\uB354\uD790", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", 35.1541279, 129.1188160)
    local = _local(
        "\uC628\uB354\uD790 \uAD11\uC548\uC810",
        "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5 1\uCE35",
        "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uC218\uC601\uAD6C \uAD11\uC548\uD574\uBCC0\uB85C 225 1\uCE35",
        35.1540727,
        129.1187239,
    )
    result = business_match(place, local)
    assert (result.matched, result.reason, result.relaxed_name) == (True, "MATCHED", True)


@pytest.mark.parametrize("naver_name,naver_address", [
    ("\uC628\uB354\uD790 \uD574\uC6B4\uB300\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 192-5"),
    ("\uC628\uB354\uD790 \uAD11\uC548\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5"),
])
def test_naver_only_branch_rejects_wrong_address_region_or_different_on_the_hill_branch(naver_name, naver_address):
    place = MatchPlace(513, "\uC628\uB354\uD790", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", 35.1541279, 129.1188160)
    if "\uAD11\uC548" in naver_name:
        place.address = "\uBD80\uC0B0 \uD574\uC6B4\uB300\uAD6C \uC6B0\uB3D9 192-5"
    result = business_match(place, _local(naver_name, naver_address, naver_address, 35.1541279, 129.1188160))
    assert (result.matched, result.reason) == (False, "NAME")


def test_naver_only_branch_rejects_similar_name_in_same_building():
    place = MatchPlace(513, "\uC628\uB354\uD790", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", 35.1541279, 129.1188160)
    local = _local("\uC628\uB354\uD790\uCE74\uD398 \uAD11\uC548\uC810", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", "\uBD80\uC0B0\uAD11\uC5ED\uC2DC \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", 35.1541279, 129.1188160)
    assert (business_match(place, local).matched, business_match(place, local).reason) == (False, "NAME")


def test_naver_only_branch_does_not_override_existing_starbucks_different_branch_block():
    place = MatchPlace(1, "\uC2A4\uD0C0\uBC85\uC2A4 \uD558\uBC84\uD0C0\uC6B4\uC810", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5")
    local = _local("\uC2A4\uD0C0\uBC85\uC2A4 \uAD11\uC548\uBE44\uCE58\uC810", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5", "\uBD80\uC0B0 \uC218\uC601\uAD6C \uAD11\uC548\uB3D9 192-5")
    assert (business_match(place, local).matched, business_match(place, local).reason) == (False, "NAME")
