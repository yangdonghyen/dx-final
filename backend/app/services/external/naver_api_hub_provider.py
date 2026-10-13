"""Small, separate client for NAVER Search API (not NAVER Login OAuth)."""

from __future__ import annotations

import html
import json
import re
import socket
from dataclasses import dataclass
from datetime import date
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import AppError

# NAVER API HUB gateway.  This is intentionally not the legacy Developers
# Open API host, and its NCP headers use the API-HUB credentials.
NAVER_SEARCH_BASE_URL = "https://naverapihub.apigw.ntruss.com/search/v1"
_TAGS = re.compile(r"<[^>]*>")


def _urlopen_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    with urlopen(Request(url, headers=headers, method="GET"), timeout=timeout) as response:
        return response.status, response.read()


def clean_search_text(value: object) -> str:
    """Treat API search text as untrusted data, never instructions or markup."""
    return html.unescape(_TAGS.sub("", value if isinstance(value, str) else "")).strip()


@dataclass(frozen=True)
class NaverLocalPlace:
    name: str
    category: str
    address: str
    road_address: str
    latitude: float | None
    longitude: float | None


@dataclass(frozen=True)
class NaverBlogPost:
    title: str
    summary: str
    published_on: date | None
    link: str


class NaverCafeEvidenceProvider(Protocol):
    def search_local(self, query: str) -> list[NaverLocalPlace]: ...
    def search_blog(self, query: str, limit: int = 5) -> list[NaverBlogPost]: ...


class UnavailableNaverCafeEvidenceProvider:
    """No network fallback: absence of review evidence must never be invented."""
    def search_local(self, query: str) -> list[NaverLocalPlace]: return []
    def search_blog(self, query: str, limit: int = 5) -> list[NaverBlogPost]: return []


class NaverApiHubProvider:
    """NAVER Search API adapter using API-HUB credentials only."""
    def __init__(self, client_id: str, client_secret: str, timeout: float,
                 http_get: Callable[[str, dict[str, str], float], tuple[int, bytes]] | None = None):
        self.client_id, self.client_secret, self.timeout = client_id, client_secret, timeout
        self.http_get = http_get or _urlopen_get

    def _request(self, resource: str, params: dict) -> dict:
        if not self.client_id or not self.client_secret:
            raise AppError("NAVER_API_HUB_NOT_CONFIGURED", "NAVER Search API credentials are not configured", 503)
        url = f"{NAVER_SEARCH_BASE_URL}/{resource}?{urlencode({**params, 'format': 'json'})}"
        try:
            status, body = self.http_get(url, {
                "X-NCP-APIGW-API-KEY-ID": self.client_id,
                "X-NCP-APIGW-API-KEY": self.client_secret,
            }, self.timeout)
        except HTTPError as error:
            status, body = error.code, b""
        except (TimeoutError, socket.timeout):
            raise AppError("NAVER_API_HUB_TIMEOUT", "NAVER Search API timed out", 504) from None
        except URLError:
            raise AppError("NAVER_API_HUB_NETWORK_ERROR", "NAVER Search API is unavailable", 502) from None
        if status in {401, 403}:
            raise AppError("NAVER_API_HUB_AUTH_FAILED", "NAVER Search API authentication failed", 502)
        if status == 429:
            raise AppError("NAVER_API_HUB_RATE_LIMITED", "NAVER Search API rate limit exceeded", 429)
        if status >= 500:
            raise AppError("NAVER_API_HUB_SERVER_ERROR", "NAVER Search API failed", 502)
        if not 200 <= status < 300:
            raise AppError("NAVER_API_HUB_ERROR", "NAVER Search API failed", 502)
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError
            return payload
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise AppError("NAVER_API_HUB_MALFORMED_RESPONSE", "NAVER Search API returned invalid data", 502) from None

    @staticmethod
    def _coordinate(value: object) -> float | None:
        try:
            coordinate = float(value)
            # API HUB describes WGS84 longitude/latitude.  Its documented
            # migration example uses fixed-point WGS84 (x10,000,000), while
            # some compatible responses expose decimal degrees.  Accept only
            # those two representations; malformed coordinates stay unknown.
            if abs(coordinate) > 180:
                coordinate /= 10_000_000
            return coordinate if -180 <= coordinate <= 180 else None
        except (TypeError, ValueError):
            return None

    def search_local(self, query: str) -> list[NaverLocalPlace]:
        payload = self._request("local", {"query": query, "display": 5})
        result = []
        for row in payload["items"]:
            if not isinstance(row, dict):
                continue
            name = clean_search_text(row.get("title"))
            if not name:
                continue
            latitude, longitude = self._coordinate(row.get("mapy")), self._coordinate(row.get("mapx"))
            if latitude is None or longitude is None or not -90 <= latitude <= 90:
                latitude = longitude = None
            result.append(NaverLocalPlace(name, clean_search_text(row.get("category")), clean_search_text(row.get("address")), clean_search_text(row.get("roadAddress")), latitude, longitude))
        return result

    def search_blog(self, query: str, limit: int = 5) -> list[NaverBlogPost]:
        payload = self._request("blog", {"query": query, "display": max(1, min(limit, 100)), "sort": "date"})
        result = []
        for row in payload["items"]:
            if not isinstance(row, dict):
                continue
            raw_date = row.get("postdate")
            try:
                published = date.fromisoformat(str(raw_date))
            except ValueError:
                published = None
            result.append(NaverBlogPost(clean_search_text(row.get("title")), clean_search_text(row.get("description")), published, str(row.get("link") or "")))
        return result
