"""Small reusable transport for local Ollama chat calls."""

import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.exceptions import AppError


def _urlopen_post(url: str, body: bytes, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


class OllamaClient:
    def __init__(self, base_url: str, timeout: float, http_post: Callable[[str, bytes, dict[str, str], float], tuple[int, bytes]] | None = None):
        if not isinstance(base_url, str) or not base_url.strip():
            raise AppError("EXAONE_BASE_URL_NOT_CONFIGURED", "EXAONE base URL is required for real preference analysis", 503)
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout
        self.http_post = http_post or _urlopen_post

    def chat(self, *, model: str, messages: list[dict[str, str]], format_schema: dict | None = None, options: dict | None = None) -> dict:
        payload = {"model": model, "messages": messages, "stream": False}
        if format_schema is not None:
            payload["format"] = format_schema
        if options is not None:
            payload["options"] = options
        try:
            status, body = self.http_post(f"{self.base_url}/api/chat", json.dumps(payload, ensure_ascii=False).encode("utf-8"), {"Content-Type": "application/json; charset=utf-8"}, self.timeout)
        except HTTPError as error:
            status, body = error.code, b""
        except (TimeoutError, socket.timeout):
            raise AppError("OLLAMA_TIMEOUT", "Ollama request timed out", 504) from None
        except URLError:
            raise AppError("OLLAMA_NETWORK_ERROR", "Ollama is unavailable", 502) from None
        if 400 <= status < 500:
            raise AppError("OLLAMA_CLIENT_ERROR", "Ollama rejected the request", 502)
        if status >= 500:
            raise AppError("OLLAMA_SERVER_ERROR", "Ollama request failed", 502)
        if status < 200 or status >= 300:
            raise AppError("OLLAMA_API_ERROR", "Ollama request failed", 502)
        try:
            response = json.loads(body.decode("utf-8"))
            if not isinstance(response, dict):
                raise ValueError
            return response
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise AppError("OLLAMA_MALFORMED_RESPONSE", "Ollama returned an invalid response", 502) from None
