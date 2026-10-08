import json
from urllib.parse import parse_qs, urlsplit

from app.core.config import Settings
from app.services.external.factory import get_route_provider
from app.services.external.routing import KakaoMobilityRouteProvider, UnavailableRouteProvider


class HttpGet:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload if payload is not None else {"routes": [{"result_code": 0, "summary": {"duration": 321}}]}
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        return self.status, json.dumps(self.payload).encode("utf-8")


def test_car_route_keeps_mobility_duration_without_walking_estimate():
    http_get = HttpGet(payload={"routes": [{"result_code": 0, "summary": {"duration": 725}}]})
    estimate = KakaoMobilityRouteProvider("test-key", 3, http_get=http_get).route(37.5, 127.0, 37.6, 127.1, "CAR")

    assert (estimate.duration_seconds, estimate.mode, estimate.walking_seconds) == (725, "CAR", None)
    url, headers, timeout = http_get.calls[0]
    assert urlsplit(url).netloc == "apis-navi.kakaomobility.com"
    assert urlsplit(url).path == "/v1/directions"
    assert parse_qs(urlsplit(url).query) == {
        "origin": ["127.000000000000,37.500000000000"],
        "destination": ["127.100000000000,37.600000000000"],
        "summary": ["true"],
    }
    assert headers == {"Authorization": "KakaoAK test-key"}
    assert timeout == 3


def test_explicit_walk_uses_map_wgs84_and_accessible_policy():
    http_get = HttpGet(payload={"status": "OK", "route": {"properties": {"totalTime": 180}}})
    provider = KakaoMobilityRouteProvider("test-key", 3, walking_route_mode="ACCESSIBLE", http_get=http_get)

    estimate = provider.route(37.5, 127.0, 37.6, 127.1, "WALK")

    assert (estimate.duration_seconds, estimate.mode, estimate.walking_seconds) == (180, "WALK", 180)
    url, headers, _ = http_get.calls[0]
    assert urlsplit(url).netloc == "dapi.kakao.com"
    assert urlsplit(url).path == "/v2/routing/walk"
    assert parse_qs(urlsplit(url).query) == {
        "start_x": ["127.000000000000"], "start_y": ["37.500000000000"],
        "end_x": ["127.100000000000"], "end_y": ["37.600000000000"],
        "input_coord": ["WGS84"], "output_coord": ["WGS84"],
        "route_mode": ["ACCESSIBLE"],
    }
    assert headers == {"Authorization": "KakaoAK test-key"}


def test_public_transit_selects_shortest_then_fewest_transfers_and_sums_walking():
    http_get = HttpGet(payload={"status": "OK", "routes": [
        {"properties": {"totalTime": 240, "transfers": 3}, "steps": [{"properties": {"type": "WALKING", "time": 120}}]},
        {"properties": {"totalTime": 240, "transfers": 1}, "steps": [
            {"properties": {"type": "WALKING", "time": 40}},
            {"properties": {"type": "BUS", "time": 120}},
            {"properties": {"type": "WALKING", "time": 30}},
        ]},
        {"properties": {"totalTime": 300, "transfers": 0}, "steps": [{"properties": {"type": "WALKING", "time": 5}}]},
    ]})

    estimate = KakaoMobilityRouteProvider("test-key", 3, http_get=http_get).route(37.5, 127.0, 37.6, 127.1, "PUBLIC_TRANSIT")

    assert (estimate.duration_seconds, estimate.mode, estimate.walking_seconds, estimate.transfer_count) == (240, "PUBLIC_TRANSIT", 70, 1)
    url, _, _ = http_get.calls[0]
    assert urlsplit(url).netloc == "dapi.kakao.com"
    assert urlsplit(url).path == "/v2/routing/publictraffic"
    assert parse_qs(urlsplit(url).query)["start_x"] == ["127.000000000000"]
    assert parse_qs(urlsplit(url).query)["start_y"] == ["37.500000000000"]


def test_incomplete_transit_walking_keeps_walking_unknown_but_preserves_total_time():
    http_get = HttpGet(payload={"status": "OK", "routes": [{
        "properties": {"totalTime": 300, "transfers": 0},
        "steps": [{"properties": {"type": "WALKING"}}],
    }]})

    estimate = KakaoMobilityRouteProvider("test-key", 3, http_get=http_get).route(37.5, 127.0, 37.6, 127.1, "PUBLIC_TRANSIT")

    assert (estimate.duration_seconds, estimate.walking_seconds, estimate.transfer_count) == (300, None, 0)


def test_other_mixed_and_invalid_or_incomplete_route_results_remain_unknown():
    http_get = HttpGet()
    provider = KakaoMobilityRouteProvider("test-key", 3, http_get=http_get)

    assert provider.route(37.5, 127.0, 37.6, 127.1, "OTHER") is None
    assert provider.route(37.5, 127.0, 37.6, 127.1, "MIXED") is None
    assert http_get.calls == []
    assert KakaoMobilityRouteProvider("test-key", 3, http_get=HttpGet(payload={"status": "NO_RESULTS"})).route(37.5, 127.0, 37.6, 127.1, "WALK") is None
    assert KakaoMobilityRouteProvider("test-key", 3, http_get=HttpGet(payload={"status": "OK", "routes": []})).route(37.5, 127.0, 37.6, 127.1, "PUBLIC_TRANSIT") is None
    no_call = HttpGet()
    assert KakaoMobilityRouteProvider("test-key", 3, http_get=no_call).route(91, 127.0, 37.6, 127.1, "PUBLIC_TRANSIT") is None
    assert no_call.calls == []


def test_route_factory_is_opt_in_and_exposes_map_walking_policy():
    assert isinstance(get_route_provider(Settings()), UnavailableRouteProvider)
    provider = get_route_provider(Settings(route_provider="kakao", kakao_rest_api_key="test-key", kakao_map_walking_route_mode="ACCESSIBLE"))
    assert isinstance(provider, KakaoMobilityRouteProvider)
    assert provider.walking_route_mode == "ACCESSIBLE"
