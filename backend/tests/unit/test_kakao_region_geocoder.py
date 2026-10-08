import json

from app.services.external.place.kakao_provider import KakaoPlaceProvider


def test_region_geocoder_accepts_only_one_exact_region_result():
    def fake_get(url, headers, timeout):
        return 200, json.dumps({"documents": [
            {"address_type": "REGION", "address_name": "부산광역시", "x": "129.0756", "y": "35.1796"},
            {"address_type": "ROAD_ADDR", "address_name": "부산로", "x": "127.0", "y": "37.0"},
        ]}).encode()

    provider = KakaoPlaceProvider("test-key", 1, fake_get)
    assert provider.resolve_region("부산") == (35.1796, 129.0756)
