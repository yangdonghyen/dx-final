import json

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.external.factory import get_scene_recognition_provider
from app.services.external.scene.gemini_provider import GeminiSceneProvider
from app.services.external.scene.mock_provider import MockSceneRecognitionProvider


def _gemini_body(text):
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()


def test_gemini_scene_provider_parses_json_and_code_fences():
    result_json = json.dumps({
        "recognized": True,
        "primary_candidate": {"place_name": "성산일출봉", "city": "서귀포시", "region": "제주특별자치도", "country": "대한민국", "category": "관광지"},
        "candidates": [{"place_name": "성산일출봉", "city": "서귀포시", "region": "제주특별자치도", "country": "대한민국", "category": "관광지"}],
        "evidence": ["화산 분화구"],
        "confidence": "HIGH",
        "needs_verification": True,
    })
    provider = GeminiSceneProvider("test-key", "gemini-test", 1, lambda url, body, timeout: (200, _gemini_body(f"```json\n{result_json}\n```")))

    result = provider.recognize_scene(b"image", "image/jpeg")

    assert result.recognized is True
    assert result.primary_candidate.place_name == "성산일출봉"
    assert result.confidence == "HIGH"


def test_gemini_scene_provider_returns_safe_error_for_invalid_json():
    provider = GeminiSceneProvider("test-key", "gemini-test", 1, lambda url, body, timeout: (200, _gemini_body("not json")))

    with pytest.raises(AppError, match="Unable to analyze") as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == "GEMINI_MALFORMED_RESPONSE"


def test_gemini_scene_provider_returns_safe_error_for_timeout():
    def timeout(*args):
        raise TimeoutError

    provider = GeminiSceneProvider("test-key", "gemini-test", 1, timeout)
    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")
    assert error.value.code == "GEMINI_TIMEOUT"


def test_gemini_scene_provider_accepts_optional_fields_and_nonfirst_text_part():
    response_body = json.dumps({
        "candidates": [{"content": {"parts": [
            {"thought": "internal"},
            {"text": json.dumps({
                "recognized": True,
                "primary_candidate": {"place_name": "광화문"},
            })},
        ]}}],
    }).encode()
    provider = GeminiSceneProvider(
        "test-key", "gemini-test", 1, lambda url, request, timeout: (200, response_body)
    )

    result = provider.recognize_scene(b"image", "image/jpeg")

    assert result.recognized is True
    assert result.primary_candidate.place_name == "광화문"
    assert [candidate.place_name for candidate in result.candidates] == ["광화문"]
    assert result.evidence == []
    assert result.confidence == "LOW"


def test_gemini_scene_provider_returns_safe_no_match_when_true_result_has_no_place():
    provider = GeminiSceneProvider(
        "test-key",
        "gemini-test",
        1,
        lambda url, body, timeout: (200, _gemini_body('{"recognized":true,"confidence":"HIGH"}')),
    )

    result = provider.recognize_scene(b"image", "image/jpeg")

    assert result.recognized is False
    assert result.primary_candidate is None
    assert result.confidence == "LOW"


@pytest.mark.parametrize(("status", "expected_code"), [
    (400, "GEMINI_API_ERROR"),
    (500, "GEMINI_SERVER_ERROR"),
    (503, "GEMINI_UNAVAILABLE"),
])
def test_gemini_scene_provider_maps_http_errors_safely(status, expected_code):
    provider = GeminiSceneProvider(
        "test-key",
        "gemini-test",
        1,
        lambda url, body, timeout: (status, b'{"error":{"status":"INTERNAL","message":"temporary"}}'),
    )

    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == expected_code


def test_gemini_scene_provider_logs_sanitized_rate_limit_body_and_retry_after(caplog):
    body = json.dumps({
        "error": {
            "status": "RESOURCE_EXHAUSTED",
            "message": "Quota exceeded: generate_content_requests_per_minute",
            "details": [{"quota": "RPM"}],
            "apiKey": "should-not-be-logged",
        },
    }).encode()
    provider = GeminiSceneProvider(
        "test-key",
        "gemini-test",
        1,
        lambda url, request, timeout: (429, body, "45"),
    )

    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == "GEMINI_RATE_LIMITED"
    assert "GEMINI_RATE_LIMITED" in caplog.text
    assert "status=429" in caplog.text
    assert "generate_content_requests_per_minute" in caplog.text
    assert "retry_after=45" in caplog.text
    assert "should-not-be-logged" not in caplog.text


def test_gemini_scene_provider_retries_a_transient_unavailable_response_once():
    calls = 0

    def post(url, body, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            return 503, b'{"error":{"status":"UNAVAILABLE","message":"busy"}}'
        return 200, _gemini_body('{"recognized":false}')

    result = GeminiSceneProvider("test-key", "gemini-test", 1, post).recognize_scene(b"image", "image/jpeg")

    assert calls == 2
    assert result.recognized is False


def test_gemini_scene_provider_primary_success_does_not_call_fallback():
    requested_models = []

    def post(url, body, timeout):
        requested_models.append(url.split("/models/", 1)[1].split(":", 1)[0])
        return 200, _gemini_body('{"recognized":false}')

    result = GeminiSceneProvider(
        "test-key", "gemini-primary", 1, post, fallback_model="gemini-fallback"
    ).recognize_scene(b"image", "image/jpeg")

    assert result.recognized is False
    assert requested_models == ["gemini-primary"]


def test_gemini_scene_provider_uses_fallback_after_primary_retry_is_unavailable():
    requested_models = []

    def post(url, body, timeout):
        model = url.split("/models/", 1)[1].split(":", 1)[0]
        requested_models.append(model)
        if model == "gemini-primary":
            return 503, b'{"error":{"status":"UNAVAILABLE","message":"busy"}}'
        return 200, _gemini_body('{"recognized":false}')

    result = GeminiSceneProvider(
        "test-key", "gemini-primary", 1, post, fallback_model="gemini-fallback"
    ).recognize_scene(b"image", "image/jpeg")

    assert result.recognized is False
    assert requested_models == ["gemini-primary", "gemini-primary", "gemini-fallback"]


def test_gemini_scene_provider_returns_unavailable_when_fallback_is_unavailable():
    requested_models = []

    def post(url, body, timeout):
        requested_models.append(url.split("/models/", 1)[1].split(":", 1)[0])
        return 503, b'{"error":{"status":"UNAVAILABLE","message":"busy"}}'

    provider = GeminiSceneProvider(
        "test-key", "gemini-primary", 1, post, fallback_model="gemini-fallback"
    )

    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == "GEMINI_UNAVAILABLE"
    assert requested_models == ["gemini-primary", "gemini-primary", "gemini-fallback"]


@pytest.mark.parametrize("status", [401, 403])
def test_gemini_scene_provider_does_not_fallback_for_auth_errors(status):
    requested_models = []

    def post(url, body, timeout):
        requested_models.append(url.split("/models/", 1)[1].split(":", 1)[0])
        return status, b'{"error":{"status":"PERMISSION_DENIED","message":"denied"}}'

    provider = GeminiSceneProvider(
        "test-key", "gemini-primary", 1, post, fallback_model="gemini-fallback"
    )

    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == "GEMINI_AUTH_FAILED"
    assert requested_models == ["gemini-primary"]


def test_gemini_scene_provider_does_not_fallback_for_malformed_primary_response():
    requested_models = []

    def post(url, body, timeout):
        requested_models.append(url.split("/models/", 1)[1].split(":", 1)[0])
        return 200, _gemini_body("not json")

    provider = GeminiSceneProvider(
        "test-key", "gemini-primary", 1, post, fallback_model="gemini-fallback"
    )

    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")

    assert error.value.code == "GEMINI_MALFORMED_RESPONSE"
    assert requested_models == ["gemini-primary"]


def test_gemini_configuration_is_required_for_real_provider():
    provider = get_scene_recognition_provider(Settings(scene_recognition_provider="real"))
    with pytest.raises(AppError) as error:
        provider.recognize_scene(b"image", "image/jpeg")
    assert error.value.code == "GEMINI_API_KEY_NOT_CONFIGURED"


def test_scene_provider_factory_uses_mock_by_default():
    assert isinstance(get_scene_recognition_provider(Settings()), MockSceneRecognitionProvider)
