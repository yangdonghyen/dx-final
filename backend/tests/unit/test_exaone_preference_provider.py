import json
import socket
from urllib.error import URLError

import pytest

from app.core.exceptions import AppError
from app.services.external.ai.exaone_preference_provider import ExaonePreferenceAnalysisProvider, PREFERENCE_FORMAT, RELEVANCE_FORMAT
from app.services.external.ai.ollama_client import OllamaClient


class Client:
    def __init__(self, responses): self.responses = list(responses if isinstance(responses, list) else [responses]); self.calls = []
    def chat(self, **kwargs): self.calls.append(kwargs); return self.responses.pop(0)


def _provider(relevance, preference=None):
    responses = [{"message": {"content": json.dumps(relevance, ensure_ascii=False)}}]
    if preference is not None: responses.append({"message": {"content": json.dumps(preference, ensure_ascii=False)}})
    client = Client(responses)
    return ExaonePreferenceAnalysisProvider("http://127.0.0.1:11434", "exaone-model", 9, client), client


def test_validates_and_normalizes_exaone_result_and_builds_strict_request():
    provider, client = _provider({"is_travel_related": True}, {"interest_codes": ["cafe", "NATURE", "CAFE"], "summary": "오션뷰 카페와 해변"})
    result = provider.analyze_preferences("오션뷰 카페와 조용한 해변")
    assert result.interest_codes == ["CAFE", "NATURE"] and result.summary == "오션뷰 카페와 해변"
    assert len(client.calls) == 2
    call = client.calls[1]
    assert call["model"] == "exaone-model" and call["options"] == {"temperature": 0} and call["format_schema"] == PREFERENCE_FORMAT
    assert call["messages"][1]["content"] == "오션뷰 카페와 조용한 해변"
    assert RELEVANCE_FORMAT["properties"]["is_travel_related"] == {"type": "boolean"}


def test_non_travel_content_returns_no_interest_codes():
    provider, client = _provider({"is_travel_related": False})
    result = provider.analyze_preferences("Rick Astley - Never Gonna Give You Up official music video lyrics")
    assert result.interest_codes == [] and result.summary == "여행 관련 관심사를 확인할 수 없습니다." and len(client.calls) == 1


@pytest.mark.parametrize(("text", "codes"), [
    ("제주 오션뷰 카페와 조용한 해변", ["CAFE", "NATURE"]),
    ("지역 유명 음식점과 미술관 전시", ["FOOD", "EXHIBITION"]),
    ("궁궐과 역사 유적, 지역 전통 공연", ["HISTORY", "CULTURE"]),
    ("시장 쇼핑, 서핑과 카약 체험", ["SHOPPING", "ACTIVITY"]),
])
def test_travel_content_uses_second_preference_classification(text, codes):
    provider, client = _provider({"is_travel_related": True}, {"interest_codes": codes, "summary": text})
    assert provider.analyze_preferences(text).interest_codes == codes and len(client.calls) == 2


def test_empty_input_is_compatible_and_skips_ollama():
    provider, client = _provider({})
    assert provider.analyze_preferences("  ").interest_codes == [] and not client.calls


@pytest.mark.parametrize("content", [
    {"interest_codes": ["COFFEE"], "summary": "카페"},
    {"interest_codes": ["FOOD", "CAFE", "NATURE", "CULTURE"], "summary": "많음"},
    {"interest_codes": "CAFE", "summary": "카페"},
    {"interest_codes": ["CAFE"], "summary": 3},
    {"summary": "누락"},
])
def test_rejects_invalid_model_output(content):
    provider, _ = _provider({"is_travel_related": True}, content)
    with pytest.raises(AppError) as error: provider.analyze_preferences("카페")
    assert error.value.code == "EXAONE_INVALID_RESPONSE"


@pytest.mark.parametrize("response", [{}, {"message": {}}, {"message": {"content": "not-json"}}, {"message": {"content": "[]"}}, {"message": {"content": "{}"}}, {"message": {"content": '{"is_travel_related":"false"}'}}])
def test_rejects_malformed_relevance_message(response):
    provider = ExaonePreferenceAnalysisProvider("http://127.0.0.1:11434", "exaone-model", 1, Client(response))
    with pytest.raises(AppError) as error: provider.analyze_preferences("카페")
    assert error.value.code == "EXAONE_INVALID_RESPONSE"


def test_requires_base_url_and_model():
    with pytest.raises(AppError) as error: ExaonePreferenceAnalysisProvider("", "model", 1)
    assert error.value.code == "EXAONE_BASE_URL_NOT_CONFIGURED"
    with pytest.raises(AppError) as error: ExaonePreferenceAnalysisProvider("http://127.0.0.1:11434", "", 1)
    assert error.value.code == "EXAONE_MODEL_NOT_CONFIGURED"


@pytest.mark.parametrize("failure,code", [
    (lambda: (400, b"{}"), "OLLAMA_CLIENT_ERROR"),
    (lambda: (500, b"{}"), "OLLAMA_SERVER_ERROR"),
    (lambda: (_ for _ in ()).throw(socket.timeout()), "OLLAMA_TIMEOUT"),
    (lambda: (_ for _ in ()).throw(URLError("offline")), "OLLAMA_NETWORK_ERROR"),
    (lambda: (200, b"not-json"), "OLLAMA_MALFORMED_RESPONSE"),
])
def test_ollama_transport_errors_are_translated(failure, code):
    client = OllamaClient("http://127.0.0.1:11434/", 7, lambda *_: failure())
    with pytest.raises(AppError) as error: client.chat(model="model", messages=[], format_schema={}, options={})
    assert error.value.code == code


def test_ollama_transport_normalizes_url_and_request_shape():
    calls = []
    def fake(url, body, headers, timeout):
        calls.append((url, json.loads(body.decode()), headers, timeout))
        return 200, b'{"message":{"content":"{}"}}'
    client = OllamaClient("http://127.0.0.1:11434/", 7, fake)
    client.chat(model="model", messages=[{"role": "user", "content": "카페"}], format_schema={"type": "object"}, options={"temperature": 0})
    assert calls[0][0] == "http://127.0.0.1:11434/api/chat" and calls[0][1]["stream"] is False and calls[0][3] == 7
