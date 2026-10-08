"""Gemini Vision adapter for recognizing place candidates from a TV scene."""

import base64
import json
import logging
import re
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.exceptions import AppError
from app.services.external.scene.provider import (
    ScenePlaceCandidate,
    SceneRecognitionResult,
)


GEMINI_GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
PROMPT = """You are a travel-screen place identifier. The input is a photo of a TV program or YouTube travel video.
Use only visible evidence in the image: landmarks, architecture, natural scenery, signs, captions, map labels, storefront names, or OCR text.
Do not invent information that cannot be seen. If a specific place cannot be identified, return recognized=false.
Return only JSON with this shape:
{
  "recognized": boolean,
  "primary_candidate": {"place_name": string, "city": string|null, "region": string|null, "country": string|null, "category": string|null}|null,
  "candidates": [{"place_name": string, "city": string|null, "region": string|null, "country": string|null, "category": string|null}],
  "evidence": [string],
  "confidence": "HIGH"|"MEDIUM"|"LOW",
  "needs_verification": true
}
Return at most three candidates. needs_verification must be true."""
logger = logging.getLogger(__name__)
_SENSITIVE_FIELD = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|credential|secret|password)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)(?:"
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|credential|secret|password)"
    r"\s*[=:]\s*[^\s,;&]+"
    r"|Bearer\s+[A-Za-z0-9._~+/=-]+"
    r"|AIza[\w-]+"
    r"|ya29\.[\w-]+"
    r"|eyJ[\w-]+(?:\.[\w-]+){2}"
    r")"
)
_MAX_LOGGED_ERROR_BODY_LENGTH = 4_000


def _urlopen_post(url: str, body: bytes, timeout: float) -> tuple[int, bytes, str | None]:
    request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read(), response.headers.get("Retry-After")


class GeminiSceneProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        http_post: Callable[[str, bytes, float], tuple[int, bytes] | tuple[int, bytes, str | None]] | None = None,
        fallback_model: str = "",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.http_post = http_post or _urlopen_post

    def recognize_scene(self, image_bytes: bytes, content_type: str) -> SceneRecognitionResult:
        if not self.api_key:
            raise AppError("GEMINI_API_KEY_NOT_CONFIGURED", "Gemini API key is not configured", 503)
        if not self.model:
            raise AppError("GEMINI_MODEL_NOT_CONFIGURED", "Gemini model is not configured", 503)
        payload = {
            "contents": [{"parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": content_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
            ]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        request_body = json.dumps(payload).encode("utf-8")
        try:
            status, body, retry_after = self._request_model_with_one_unavailable_retry(self.model, request_body)
            if status == 503 and self._has_distinct_fallback_model():
                logger.warning("Gemini primary model unavailable; trying fallback model")
                status, body, retry_after = self._request_model_once(self.fallback_model, request_body)
                if 200 <= status < 300:
                    logger.info("Gemini fallback model request succeeded")
                else:
                    logger.warning("Gemini fallback model request failed: status=%s", status)
        except (TimeoutError, socket.timeout):
            raise AppError("GEMINI_TIMEOUT", "Unable to analyze the place. Please try again.", 504) from None
        except URLError:
            raise AppError("GEMINI_NETWORK_ERROR", "Unable to analyze the place. Please try again.", 502) from None
        if status < 200 or status >= 300:
            logger.warning(
                "Gemini API request failed: status=%s reason=%s",
                status,
                self._error_reason(body),
            )
        if status in {401, 403}:
            raise AppError("GEMINI_AUTH_FAILED", "Unable to analyze the place. Please try again.", 502)
        if status == 429:
            logger.warning(
                "GEMINI_RATE_LIMITED\nstatus=429\nmessage=%s\nretry_after=%s",
                self._safe_error_body(body),
                self._safe_retry_after(retry_after),
            )
            raise AppError("GEMINI_RATE_LIMITED", "Unable to analyze the place. Please try again.", 429)
        if status == 503:
            raise AppError("GEMINI_UNAVAILABLE", "Unable to analyze the place. Please try again.", 503)
        if status >= 500:
            raise AppError("GEMINI_SERVER_ERROR", "Unable to analyze the place. Please try again.", 502)
        if status < 200 or status >= 300:
            raise AppError("GEMINI_API_ERROR", "Unable to analyze the place. Please try again.", 502)
        try:
            response = json.loads(body.decode("utf-8"))
            text = self._response_text(response)
            return self._parse_result(text)
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
            raise AppError("GEMINI_MALFORMED_RESPONSE", "Unable to analyze the place. Please try again.", 502) from None

    def _has_distinct_fallback_model(self) -> bool:
        return bool(self.fallback_model and self.fallback_model != self.model)

    def _request_model_with_one_unavailable_retry(self, model: str, body: bytes) -> tuple[int, bytes, str | None]:
        for attempt in range(2):
            status, response_body, retry_after = self._request_model_once(model, body)
            if status != 503 or attempt == 1:
                return status, response_body, retry_after
        raise AssertionError("unreachable")

    def _request_model_once(self, model: str, body: bytes) -> tuple[int, bytes, str | None]:
        url = GEMINI_GENERATE_CONTENT_URL.format(model=model) + "?key=" + self.api_key
        try:
            response = self.http_post(url, body, self.timeout)
            if len(response) == 2:
                status, response_body = response
                return status, response_body, None
            return response
        except HTTPError as error:
            return error.code, error.read(), error.headers.get("Retry-After") if error.headers else None

    @classmethod
    def _safe_error_body(cls, body: bytes) -> str:
        """Return a bounded diagnostic body without credentials or tokens."""
        try:
            decoded = body.decode("utf-8")
        except UnicodeDecodeError:
            return "<non-utf8 error body>"

        try:
            decoded = json.dumps(cls._redact_sensitive_fields(json.loads(decoded)), ensure_ascii=False, separators=(",", ":"))
        except json.JSONDecodeError:
            pass
        decoded = decoded.replace("\r", "\\r").replace("\n", "\\n")
        decoded = _SENSITIVE_VALUE.sub("[REDACTED]", decoded)
        if len(decoded) > _MAX_LOGGED_ERROR_BODY_LENGTH:
            return decoded[:_MAX_LOGGED_ERROR_BODY_LENGTH] + "…[truncated]"
        return decoded

    @classmethod
    def _redact_sensitive_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if _SENSITIVE_FIELD.search(str(key)) else cls._redact_sensitive_fields(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact_sensitive_fields(item) for item in value]
        return value

    @staticmethod
    def _safe_retry_after(value: str | None) -> str:
        if not value:
            return ""
        return _SENSITIVE_VALUE.sub("[REDACTED]", value.replace("\r", " ").replace("\n", " "))[:200]

    @staticmethod
    def _error_reason(body: bytes) -> str:
        """Extract diagnostic metadata only; never log request data or credentials."""
        try:
            error = json.loads(body.decode("utf-8")).get("error", {})
            status = error.get("status")
            message = error.get("message")
            if isinstance(status, str) and isinstance(message, str):
                return f"{status}: {_SENSITIVE_VALUE.sub('[REDACTED]', message)[:200]}"
            if isinstance(status, str):
                return status
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            pass
        return "unavailable"

    @staticmethod
    def _response_text(response: object) -> str:
        if not isinstance(response, dict):
            raise ValueError
        candidates = response.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError
        for candidate in candidates:
            content = candidate.get("content") if isinstance(candidate, dict) else None
            parts = content.get("parts") if isinstance(content, dict) else None
            if not isinstance(parts, list):
                continue
            for part in parts:
                text = part.get("text") if isinstance(part, dict) else None
                if isinstance(text, str) and text.strip():
                    return text
        raise ValueError

    @classmethod
    def _parse_result(cls, text: object) -> SceneRecognitionResult:
        if not isinstance(text, str):
            raise ValueError
        text = text.strip()
        fence_start = text.find("```")
        if fence_start >= 0:
            fenced = text[fence_start + 3 :]
            fenced = fenced.split("\n", 1)[1] if "\n" in fenced else ""
            fence_end = fenced.find("```")
            text = fenced if fence_end < 0 else fenced[:fence_end]
        else:
            json_start, json_end = text.find("{"), text.rfind("}")
            if json_start >= 0 and json_end >= json_start:
                text = text[json_start : json_end + 1]
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError
        recognized = data.get("recognized")
        if not isinstance(recognized, bool):
            raise ValueError
        if not recognized:
            return SceneRecognitionResult(False, None, [], [], "LOW")
        confidence = data.get("confidence")
        confidence = confidence.upper() if isinstance(confidence, str) else "LOW"
        if confidence not in {"HIGH", "MEDIUM", "LOW"}:
            confidence = "LOW"
        candidates = cls._candidates(data.get("candidates"))
        primary = cls._candidate(data.get("primary_candidate"))
        evidence = data.get("evidence")
        evidence = (
            [item.strip() for item in evidence if isinstance(item, str) and item.strip()][:10]
            if isinstance(evidence, list)
            else []
        )
        if primary is None and candidates:
            primary = candidates[0]
        if primary is not None and not candidates:
            candidates = [primary]
        if primary is None:
            return SceneRecognitionResult(False, None, [], evidence, "LOW")
        return SceneRecognitionResult(True, primary, candidates, evidence, confidence)

    @classmethod
    def _candidates(cls, value: object) -> list[ScenePlaceCandidate]:
        if not isinstance(value, list):
            return []
        return [candidate for item in value if (candidate := cls._candidate(item)) is not None][:3]

    @staticmethod
    def _candidate(value: object) -> ScenePlaceCandidate | None:
        if value is None:
            return None
        if not isinstance(value, dict) or not isinstance(value.get("place_name"), str) or not value["place_name"].strip():
            return None
        fields = ("city", "region", "country", "category")
        return ScenePlaceCandidate(
            place_name=value["place_name"].strip(),
            city=value.get("city") if isinstance(value.get("city"), str) else None,
            region=value.get("region") if isinstance(value.get("region"), str) else None,
            country=value.get("country") if isinstance(value.get("country"), str) else None,
            category=value.get("category") if isinstance(value.get("category"), str) else None,
        )
