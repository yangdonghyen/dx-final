from app.services.external.place.tour_destination_image_provider import (
    TourDestinationImageProvider,
)
from app.services.youtube_destination_resolver import YouTubeDestinationResolver


def _payload(rows, total=None):
    body = {"items": {"item": rows}}
    if total is not None:
        body["totalCount"] = total
    return {"response": {"header": {"resultCode": "0000"}, "body": body}}


PROVINCES = [
    {"name": "서울", "code": "1"},
    {"name": "부산", "code": "6"},
    {"name": "세종특별자치시", "code": "8"},
    {"name": "경기도", "code": "31"},
    {"name": "강원특별자치도", "code": "32"},
]
GYEONGGI = [{"name": "가평군", "code": "1"}, {"name": "수원시", "code": "13"}]


def _provider(calls):
    provider = TourDestinationImageProvider("unused", "https://example.test", 1)

    def fake_get_json(endpoint, params):
        calls.append((endpoint, dict(params)))
        if endpoint == "areaCode2":
            return _payload(GYEONGGI if params.get("areaCode") == "31" else PROVINCES)
        return _payload([{
            "contentid": "100", "title": "화성행궁", "firstimage": "http://img/1.jpg",
            "contenttypeid": "12", "addr1": "경기도 수원시",
        }], total=1)

    provider._get_json = fake_get_json
    return provider


def test_city_destination_searches_its_sigungu_inside_the_province():
    calls = []
    candidates = _provider(calls).search_candidates("수원", limit=10)

    assert [candidate.title for candidate in candidates] == ["화성행궁"]
    area_calls = [params for endpoint, params in calls if endpoint == "areaBasedList2"]
    assert area_calls[0]["areaCode"] == "31"
    assert area_calls[0]["sigunguCode"] == "13"


def test_province_destination_matches_by_prefix_without_sigungu():
    calls = []
    _provider(calls).search_candidates("세종", limit=10)

    area_calls = [params for endpoint, params in calls if endpoint == "areaBasedList2"]
    assert area_calls[0]["areaCode"] == "8"
    assert "sigunguCode" not in area_calls[0]


def test_unknown_destination_returns_no_candidates():
    calls = []
    assert _provider(calls).search_candidates("나혼자 수원 브이로그", limit=10) == []
    assert not [endpoint for endpoint, _ in calls if endpoint == "areaBasedList2"]


def test_suwon_title_resolves_to_suwon():
    title = "나혼자 수원🚀혼자 열기구타고 왕갈비통닭 냠 (수원맛집)수원 여행 브이로그"
    assert YouTubeDestinationResolver().resolve(title) == "수원"
    assert set(YouTubeDestinationResolver.PROVINCES) <= set(YouTubeDestinationResolver._DESTINATIONS)
