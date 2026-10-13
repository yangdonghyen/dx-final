"""Ollama timing, timeout and malformed-answer handling for plan generation.

No real Ollama call: the HTTP layer of OllamaClient is replaced.
"""

import json
import socket
import time

import pytest

from app.core.exceptions import AppError
from app.services.external.ai.exaone_plan_provider import (
    MAX_SCHEMA_RETRY_MODEL_CALLS,
    PLAN_OUTPUT_BASE_TOKENS,
    PLAN_OUTPUT_TOKENS_PER_DAY,
    ExaonePlanGenerationProvider,
)
from app.services.external.ai.ollama_client import OllamaClient

STATS = {
    "load_duration": 2_000_000_000,
    "prompt_eval_count": 3100,
    "prompt_eval_duration": 40_000_000_000,
    "eval_count": 420,
    "eval_duration": 35_000_000_000,
    "done_reason": "stop",
}


def _plan():
    return json.dumps({"days": [
        {"visit_date": "2026-10-10", "items": [
            {"sequence": 1, "item_type": "PLACE", "title": "경포대", "place_id": 101, "start_time": "10:00", "end_time": "11:00"},
        ]},
        {"visit_date": "2026-10-11", "items": [
            {"sequence": 1, "item_type": "REST", "title": "휴식", "place_id": None, "start_time": "10:00", "end_time": "11:00"},
        ]},
    ]}, ensure_ascii=False)


def _inputs():
    return (
        {"destination": "강릉", "start_date": "2026-10-10", "end_date": "2026-10-11", "budget_krw": 300000},
        {"walking_tolerance": "LOW", "rest_frequency": "HIGH", "taxi_allowed": True, "travel_style": "STANDARD"},
        [], ["CAFE", "FOOD"], {"raw_interest_codes": ["CITY"]},
        [{"place_id": 101, "name": "경포대", "category": "관광명소", "region": "강원특별자치도 강릉시", "address": "강원특별자치도 강릉시 저동"}],
    )


class Http:
    """Stands in for the urllib POST used by OllamaClient."""

    def __init__(self, *answers, delay=0.0):
        self.answers = list(answers)
        self.delay = delay
        self.calls = []

    def __call__(self, url, body, headers, timeout):
        self.calls.append({"url": url, "payload": json.loads(body), "timeout": timeout})
        if self.delay:
            time.sleep(self.delay)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return 200, answer


def _ollama(content, **stats):
    return json.dumps({"message": {"content": content}, **STATS, **stats}, ensure_ascii=False).encode("utf-8")


def _provider(http, timeout=180):
    client = OllamaClient("http://127.0.0.1:11434", timeout, http_post=http)
    return ExaonePlanGenerationProvider("http://127.0.0.1:11434", "exaone-test", timeout, client)


def _call_logs(caplog):
    return [row.getMessage() for row in caplog.records if "exaone_model_call" in row.getMessage()]


def test_normal_answer_bounds_output_and_logs_where_time_went(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama(_plan()))

    draft = _provider(http).generate_plan(*_inputs())

    assert [len(day.items) for day in draft.days] == [1, 1]
    sent = http.calls[0]
    assert sent["timeout"] == 180
    assert sent["payload"]["stream"] is False
    assert sent["payload"]["options"] == {
        "temperature": 0,
        "num_ctx": 8192,
        "num_predict": PLAN_OUTPUT_BASE_TOKENS + 2 * PLAN_OUTPUT_TOKENS_PER_DAY,
    }
    [line] = _call_logs(caplog)
    for part in ("call=1/2", "timeout_s=180", "error=None", "days=2", "candidates=1",
                 "load_ms=2000", "prompt_tokens=3100", "prompt_ms=40000",
                 "output_tokens=420", "output_ms=35000", "done_reason=stop"):
        assert part in line
    # Sizes only; no place names or prompt text in the log.
    assert "경포대" not in line


def test_slow_answer_inside_the_timeout_still_succeeds(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama(_plan()), delay=0.2)

    draft = _provider(http, timeout=5).generate_plan(*_inputs())

    assert len(draft.days) == 2
    assert len(http.calls) == 1
    elapsed = int(_call_logs(caplog)[0].split("elapsed_ms=")[1].split()[0])
    assert elapsed >= 200


def test_timeout_is_reported_once_without_a_second_model_call(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(socket.timeout("timed out"), _ollama(_plan()))

    with pytest.raises(AppError) as error:
        _provider(http).generate_plan(*_inputs())

    assert (error.value.code, error.value.status_code) == ("OLLAMA_TIMEOUT", 504)
    assert len(http.calls) == 1
    [line] = _call_logs(caplog)
    assert "error=OLLAMA_TIMEOUT" in line and "timeout_s=180" in line
    assert "prompt_tokens=None" in line


def test_non_json_ollama_body_is_a_clear_provider_error():
    http = Http(b"<html>proxy error</html>")

    with pytest.raises(AppError) as error:
        _provider(http).generate_plan(*_inputs())

    assert error.value.code == "OLLAMA_MALFORMED_RESPONSE"
    assert len(http.calls) == 1


def test_invalid_plan_json_is_retried_once_then_rejected(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama('{"days": ['), _ollama("not json"))

    with pytest.raises(AppError) as error:
        _provider(http).generate_plan(*_inputs())

    assert error.value.code == "EXAONE_INVALID_RESPONSE"
    assert len(http.calls) == MAX_SCHEMA_RETRY_MODEL_CALLS
    assert len(_call_logs(caplog)) == MAX_SCHEMA_RETRY_MODEL_CALLS


def test_answer_cut_by_the_output_bound_is_logged_and_retried(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama('{"days": [{"visit_date"', done_reason="length"), _ollama(_plan()))

    draft = _provider(http).generate_plan(*_inputs())

    assert len(draft.days) == 2
    first, second = _call_logs(caplog)
    assert "done_reason=length" in first
    assert "done_reason=stop" in second


def _validation_logs(caplog):
    return [row.getMessage() for row in caplog.records if "exaone_model_validation" in row.getMessage()]


def _duplicate_place_plan():
    return json.dumps({"days": [
        {"visit_date": "2026-10-10", "items": [
            {"sequence": 1, "item_type": "PLACE", "title": "경포대", "place_id": 101, "start_time": "10:00", "end_time": "11:00"},
        ]},
        {"visit_date": "2026-10-11", "items": [
            {"sequence": 1, "item_type": "PLACE", "title": "경포대", "place_id": 101, "start_time": "10:00", "end_time": "11:00"},
        ]},
    ]}, ensure_ascii=False)


def test_validation_reason_is_logged_and_kept_per_call(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama(_duplicate_place_plan()), _ollama(_plan()))
    provider = _provider(http)

    provider.generate_plan(*_inputs())

    first, second = provider.call_diagnostics
    assert first["result"] == "invalid" and first["error_code"] == "EXAONE_INVALID_RESPONSE"
    assert first["validation_reason"].startswith("duplicate_place_id:101")
    assert first["will_retry"] is True
    assert second == {"call": 2, "result": "valid", "error_code": None, "validation_reason": None, "will_retry": False, "done_reason": "stop"}
    logs = _validation_logs(caplog)
    assert "result=invalid" in logs[0] and "validation_reason=duplicate_place_id:101" in logs[0] and "will_retry=True" in logs[0]
    assert "result=valid" in logs[1]
    # Codes only: no prompt or answer text reaches the diagnostic line.
    assert not any("경포대" in line or "Backend validation error" in line for line in logs)


def test_final_invalid_answer_reports_reason_without_retry(caplog):
    caplog.set_level("INFO", logger="uvicorn.error")
    http = Http(_ollama("not json"), _ollama("not json"))
    provider = _provider(http)

    with pytest.raises(AppError) as error:
        provider.generate_plan(*_inputs())

    assert error.value.validation_reason == "json_decode"
    assert [row["will_retry"] for row in provider.call_diagnostics] == [True, False]
    assert all(row["validation_reason"] == "json_decode" for row in provider.call_diagnostics)
    assert len(_validation_logs(caplog)) == MAX_SCHEMA_RETRY_MODEL_CALLS


def test_timeout_is_recorded_as_a_failed_call():
    http = Http(socket.timeout("timed out"))
    provider = _provider(http)

    with pytest.raises(AppError) as error:
        provider.generate_plan(*_inputs())

    [row] = provider.call_diagnostics
    assert row["result"] == "failed" and row["error_code"] == error.value.code and row["will_retry"] is False
