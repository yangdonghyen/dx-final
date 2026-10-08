import json
import socket
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.exceptions import AppError
from app.services.external.content.youtube_provider import YouTubeContentProvider


def _item(tags=None):
    return {"id": "dQw4w9WgXcQ", "snippet": {"title": "Video", "description": "Description", "tags": ["travel"] if tags is None else tags, "channelId": "channel-id", "channelTitle": "Channel"}}


def _provider(status=200, payload=None):
    calls = []
    def fake(url, timeout):
        calls.append((url, timeout))
        body = payload if payload is not None else {"items": [_item()]}
        return status, json.dumps(body).encode()
    return YouTubeContentProvider("test-key", 4.5, fake), calls


def test_maps_snippet_to_existing_content_dto_and_requests_only_snippet():
    provider, calls = _provider()
    result = provider.get_video("dQw4w9WgXcQ")
    assert (result.video_id, result.title, result.description, result.tags, result.channel_id, result.channel_title) == ("dQw4w9WgXcQ", "Video", "Description", ["travel"], "channel-id", "Channel")
    query = parse_qs(urlsplit(calls[0][0]).query)
    assert query["part"] == ["snippet"] and query["id"] == ["dQw4w9WgXcQ"] and calls[0][1] == 4.5


def test_allows_videos_without_tags():
    provider, _ = _provider(payload={"items": [_item(tags=[])]})
    assert provider.get_video("dQw4w9WgXcQ").tags == []


@pytest.mark.parametrize("status,payload,code", [
    (400, {}, "YOUTUBE_API_ERROR"),
    (403, {}, "YOUTUBE_AUTH_FAILED"),
    (403, {"error": {"errors": [{"reason": "quotaExceeded"}]}}, "YOUTUBE_QUOTA_EXCEEDED"),
    (500, {}, "YOUTUBE_SERVER_ERROR"),
    (200, {"items": []}, "PROVIDER_NOT_FOUND"),
    (200, {"items": [{"id": "id", "snippet": {}}]}, "YOUTUBE_MALFORMED_RESPONSE"),
])
def test_translates_youtube_status_and_response_errors(status, payload, code):
    provider, _ = _provider(status, payload)
    with pytest.raises(AppError) as error: provider.get_video("dQw4w9WgXcQ")
    assert error.value.code == code


@pytest.mark.parametrize("failure,code", [
    (lambda: (_ for _ in ()).throw(socket.timeout()), "YOUTUBE_TIMEOUT"),
    (lambda: (_ for _ in ()).throw(URLError("offline")), "YOUTUBE_NETWORK_ERROR"),
])
def test_translates_youtube_transport_errors(failure, code):
    provider = YouTubeContentProvider("test-key", 1, lambda *_: failure())
    with pytest.raises(AppError) as error: provider.get_video("dQw4w9WgXcQ")
    assert error.value.code == code


def test_rejects_missing_key_and_blank_video_id_without_http():
    provider = YouTubeContentProvider("", 1, lambda *_: pytest.fail("must not call HTTP"))
    with pytest.raises(AppError) as error: provider.get_video("dQw4w9WgXcQ")
    assert error.value.code == "YOUTUBE_API_KEY_NOT_CONFIGURED"
    provider = YouTubeContentProvider("test-key", 1, lambda *_: pytest.fail("must not call HTTP"))
    with pytest.raises(AppError) as error: provider.get_video(" ")
    assert error.value.code == "INVALID_YOUTUBE_VIDEO_ID"
