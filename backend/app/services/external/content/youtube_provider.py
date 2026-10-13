"""YouTube Data API v3 adapter for the existing content-provider contract."""

import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import AppError
from app.services.external.content.provider import VideoMetadata


YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


def _urlopen_get(url: str, timeout: float) -> tuple[int, bytes]:
    with urlopen(Request(url, method="GET"), timeout=timeout) as response:
        return response.status, response.read()


class YouTubeContentProvider:
    def __init__(self, api_key: str, timeout: float, http_get: Callable[[str, float], tuple[int, bytes]] | None = None):
        self.api_key = api_key
        self.timeout = timeout
        self.http_get = http_get or _urlopen_get

    @staticmethod
    def _is_quota_error(body: bytes) -> bool:
        try:
            reasons = [item.get("reason") for item in json.loads(body.decode("utf-8")).get("error", {}).get("errors", [])]
            return "quotaExceeded" in reasons
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
            return False

    @staticmethod
    def _metadata(item: dict) -> VideoMetadata:
        snippet = item["snippet"]
        required = ("id",)
        snippet_required = ("title", "description", "channelId", "channelTitle")
        if not isinstance(item, dict) or any(not item.get(field) for field in required) or not isinstance(snippet, dict) or any(field not in snippet for field in snippet_required):
            raise ValueError
        tags = snippet.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError

        thumbnail_url = None
        thumbnails = snippet.get("thumbnails", {})

        if isinstance(thumbnails, dict):
            for quality in ("maxres", "standard", "high", "medium", "default"):
                thumbnail = thumbnails.get(quality)
                if isinstance(thumbnail, dict):
                    url = thumbnail.get("url")
                    if isinstance(url, str) and url:
                        thumbnail_url = url
                        break

        return VideoMetadata(
            video_id=str(item["id"]),
            title=str(snippet["title"]),
            description=str(snippet["description"]),
            tags=tags,
            channel_id=str(snippet["channelId"]),
            channel_title=str(snippet["channelTitle"]),
            thumbnail_url=thumbnail_url,
        )

    def get_video(self, video_id: str) -> VideoMetadata:
        if not isinstance(video_id, str) or not video_id.strip():
            raise AppError("INVALID_YOUTUBE_VIDEO_ID", "YouTube video ID is required", 400)
        if not self.api_key:
            raise AppError("YOUTUBE_API_KEY_NOT_CONFIGURED", "YouTube API key is not configured", 503)
        url = f"{YOUTUBE_VIDEOS_ENDPOINT}?{urlencode({'part': 'snippet', 'id': video_id.strip(), 'key': self.api_key})}"
        try:
            status, body = self.http_get(url, self.timeout)
        except HTTPError as error:
            status, body = error.code, b""
        except (TimeoutError, socket.timeout):
            raise AppError("YOUTUBE_TIMEOUT", "YouTube API timed out", 504) from None
        except URLError:
            raise AppError("YOUTUBE_NETWORK_ERROR", "YouTube API is unavailable", 502) from None
        if status == 403 and self._is_quota_error(body):
            raise AppError("YOUTUBE_QUOTA_EXCEEDED", "YouTube API quota exceeded", 429)
        if status in {401, 403}:
            raise AppError("YOUTUBE_AUTH_FAILED", "YouTube API authentication failed", 502)
        if status == 400:
            raise AppError("YOUTUBE_API_ERROR", "YouTube API rejected the request", 502)
        if status >= 500:
            raise AppError("YOUTUBE_SERVER_ERROR", "YouTube API failed", 502)
        if status < 200 or status >= 300:
            raise AppError("YOUTUBE_API_ERROR", "YouTube API failed", 502)
        try:
            payload = json.loads(body.decode("utf-8"))
            items = payload["items"]
            if not isinstance(items, list):
                raise ValueError
            if not items:
                raise LookupError
            return self._metadata(items[0])
        except LookupError:
            raise AppError("PROVIDER_NOT_FOUND", "YouTube video was not found", 404) from None
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise AppError("YOUTUBE_MALFORMED_RESPONSE", "YouTube returned an invalid video response", 502) from None

