import io
import json
import logging
from urllib.error import HTTPError

import pytest

from app.core.exceptions import AppError
from app.services.external.place.tour_destination_image_provider import (
    TourDestinationImageProvider,
)
from app.services.external.place import tour_destination_image_provider as provider_module


def _payload(rows):
    return {
        "response": {
            "header": {"resultCode": "0000"},
            "body": {"items": {"item": rows}},
        }
    }


def test_place_detail_uses_common_and_intro_data_and_normalizes_empty_values(monkeypatch):
    provider = TourDestinationImageProvider("unused", "https://example.test", 1)
    calls = []

    def fake_get_json(endpoint, params):
        calls.append((endpoint, params))
        if endpoint == "detailCommon2":
            return _payload([{
                "contentid": "12345",
                "contenttypeid": "12",
                "title": "실제 장소",
                "addr1": "실제 주소",
                "firstimage": "http://tong.visitkorea.or.kr/image.jpg",
                "overview": "<p>공식 소개</p>",
                "mapx": "129.1",
                "mapy": "35.2",
                "homepage": "",
                "cat1": "A01",
                "cat2": "A0101",
                "cat3": "A01010100",
            }])
        return _payload([{
            "usetime": "09:00~18:00",
            "restdate": "월요일",
            "usefee": "",
            "parking": "주차 안내 원문",
            "infocenter": None,
        }])

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    result = provider.get_place_detail("12345", 12)

    assert [call[0] for call in calls] == ["detailCommon2", "detailIntro2"]
    # detailCommon2's current minimal request contract needs only contentId.
    # The response fixture still verifies the common fields consumed below.
    assert calls[0][1] == {"contentId": "12345"}
    assert calls[1][1] == {"contentId": "12345", "contentTypeId": 12}
    assert result["title"] == "실제 장소"
    assert result["overview"] == "공식 소개"
    assert result["image_url"] == "https://tong.visitkorea.or.kr/image.jpg"
    assert result["map_x"] == 129.1
    assert result["map_y"] == 35.2
    assert result["operating_hours"] == "09:00~18:00"
    assert result["use_fee"] is None
    assert result["info_center"] is None


def test_place_detail_rejects_invalid_or_unknown_content_id(monkeypatch):
    provider = TourDestinationImageProvider("unused", "https://example.test", 1)
    with pytest.raises(AppError) as invalid:
        provider.get_place_detail("not-an-id")
    assert invalid.value.status_code == 400

    monkeypatch.setattr(provider, "_get_json", lambda *_args, **_kwargs: _payload([]))
    with pytest.raises(AppError) as missing:
        provider.get_place_detail("999999")
    assert missing.value.status_code == 404


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        (None, []),
        ("", []),
        ({}, []),
        ({"item": {"contentid": "127925"}}, [{"contentid": "127925"}]),
        (
            {"item": [{"contentid": "127925"}, {"contentid": "170"}]},
            [{"contentid": "127925"}, {"contentid": "170"}],
        ),
        ({"item": [{"contentid": "127925"}, None, "bad"]}, [{"contentid": "127925"}]),
    ],
)
def test_response_rows_safely_handles_supported_items_shapes(items, expected):
    payload = {"response": {"header": {"resultCode": "00"}, "body": {"items": items}}}
    assert TourDestinationImageProvider._response_rows(payload) == expected


def test_http_200_logs_safe_shape_and_parses_payload_without_header(
    monkeypatch, caplog
):
    provider = TourDestinationImageProvider("unused-secret", "https://example.test", 1)
    body = json.dumps({
        "response": {
            "body": {"items": {"item": {"contentid": "127925", "title": "실제 장소"}}}
        }
    }).encode()

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json;charset=UTF-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return body

    monkeypatch.setattr(provider_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    caplog.set_level(logging.INFO)

    payload = provider._get_json("detailCommon2", {"contentId": "127925"})
    rows = provider._response_rows(payload)

    assert rows == [{"contentid": "127925", "title": "실제 장소"}]
    assert "content_type=application/json;charset=UTF-8" in caplog.text
    assert "json_decode=true" in caplog.text
    assert "top_keys=['response']" in caplog.text
    assert "response_key_exists=True" in caplog.text
    assert "header=null" in caplog.text
    assert "body_keys=['items']" in caplog.text
    assert "items_type=dict" in caplog.text
    assert "item_type=dict" in caplog.text
    assert "item_count=1" in caplog.text
    assert "unused-secret" not in caplog.text


def test_json_decode_failure_logs_status_and_redacted_body_head(monkeypatch, caplog):
    secret = "do-not-log-this-service-key"
    provider = TourDestinationImageProvider(secret, "https://example.test", 1)

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return f"not json serviceKey={secret}".encode()

    monkeypatch.setattr(provider_module, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    with pytest.raises(AppError) as error:
        provider._get_json("detailCommon2", {"contentId": "127925"})

    assert error.value.code == "TOUR_API_MALFORMED_RESPONSE"
    assert "stage=json_decode" in caplog.text
    assert "content_id=127925" in caplog.text
    assert "status=200" in caplog.text
    assert "content_type=text/plain" in caplog.text
    assert "error_type=JSONDecodeError" in caplog.text
    assert secret not in caplog.text


def test_common_detail_survives_intro_failure(monkeypatch):
    provider = TourDestinationImageProvider("unused", "https://example.test", 1)

    def fake_get_json(endpoint, _params):
        if endpoint == "detailCommon2":
            return _payload([{
                "contentid": "127925",
                "title": "실제 관광지",
                "addr1": "실제 주소",
                "firstimage": "https://images.example/place.jpg",
                "mapx": "129.1",
                "mapy": "35.1",
            }])
        if endpoint == "detailIntro2":
            raise AppError("TOUR_API_ERROR", "intro unavailable", 502)
        raise AssertionError("image detail should not be requested when firstimage exists")

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    detail = provider.get_place_detail("127925", 12)

    assert detail["title"] == "실제 관광지"
    assert detail["address"] == "실제 주소"
    assert detail["operating_hours"] is None


def test_intro_and_common_survive_image_fallback_failure(monkeypatch):
    provider = TourDestinationImageProvider("unused", "https://example.test", 1)
    calls = []

    def fake_get_json(endpoint, params):
        calls.append((endpoint, params))
        if endpoint == "detailCommon2":
            return _payload([{
                "contentid": "127925",
                "title": "실제 관광지",
                "addr1": "실제 주소",
            }])
        if endpoint == "detailIntro2":
            return _payload([{"usetime": "09:00~18:00"}])
        if endpoint == "detailImage2":
            raise AppError("TOUR_API_ERROR", "images unavailable", 502)
        raise AssertionError(endpoint)

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    detail = provider.get_place_detail("127925", 12)

    assert [endpoint for endpoint, _ in calls] == [
        "detailCommon2", "detailIntro2", "detailImage2"
    ]
    assert calls[-1][1] == {
        "contentId": "127925",
        "imageYN": "Y",
        "subImageYN": "Y",
    }
    assert detail["title"] == "실제 관광지"
    assert detail["operating_hours"] == "09:00~18:00"
    assert detail["image_url"] is None


def test_http_error_log_includes_tour_response_without_service_key(monkeypatch, caplog):
    secret = "test-secret-value"
    provider = TourDestinationImageProvider(secret, "https://example.test", 1)
    response_body = json.dumps({
        "response": {
            "header": {
                "resultCode": "10",
                "resultMsg": f"invalid parameter: {secret}",
            }
        }
    }).encode()

    def raise_http_error(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=io.BytesIO(response_body),
        )

    monkeypatch.setattr(provider_module, "urlopen", raise_http_error)
    with pytest.raises(AppError):
        provider._get_json("detailCommon2", {"contentId": "127925"})

    log = caplog.text
    assert "endpoint=detailCommon2" in log
    assert "content_id=127925" in log
    assert "status=400" in log
    assert "resultCode=10" in log
    assert "invalid parameter" in log
    assert secret not in log


def test_tour_place_detail_http_route_returns_normalized_payload():
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.api.v1.discovery import get_tour_destination_provider
    from app.dependencies import get_current_user
    from app.main import create_app
    from app.core.config import Settings

    class StubProvider:
        def get_place_detail(self, content_id, content_type_id):
            assert content_id == "127925"
            assert content_type_id == 12
            return {
                "content_id": content_id,
                "content_type_id": content_type_id,
                "title": "검증된 관광지",
                "address": "API 원본 주소",
                "map_x": 129.1,
                "map_y": 35.1,
            }

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(user_id=3)
    app.dependency_overrides[get_tour_destination_provider] = StubProvider

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/discovery/tour-places/127925?content_type_id=12"
        )

    assert response.status_code == 200
    assert response.json() == {
        "content_id": "127925",
        "content_type_id": 12,
        "title": "검증된 관광지",
        "address": "API 원본 주소",
        "map_x": 129.1,
        "map_y": 35.1,
    }
