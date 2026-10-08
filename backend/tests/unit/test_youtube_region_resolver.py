import json

from app.core.exceptions import AppError
from app.services.external.content.provider import VideoMetadata
from app.services.youtube_region_resolver import YouTubeRegionResolver


def _video(title="브이로그", tags=None, description=""):
    return VideoMetadata(
        video_id="vid1",
        title=title,
        description=description,
        tags=tags or [],
        channel_id="ch",
        channel_title="여행채널",
    )


class _Provider:
    def __init__(self, video=None, error=None):
        self.video, self.error, self.calls = video, error, 0

    def get_video(self, video_id):
        self.calls += 1
        if self.error:
            raise self.error
        return self.video


class _Client:
    def __init__(self, region=None, error=None, raw=None):
        self.region, self.error, self.raw, self.calls = region, error, raw, []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = self.raw if self.raw is not None else json.dumps({"region": self.region}, ensure_ascii=False)
        return {"message": {"content": content}}


def _resolver(provider, client=None, model="exaone"):
    return YouTubeRegionResolver(
        content_provider_factory=lambda: provider,
        client_factory=(lambda: client) if client is not None else None,
        model=model,
    )


def test_title_keyword_skips_youtube_call():
    provider = _Provider(_video())
    assert _resolver(provider).resolve("vid1", "부산 1박2일 여행") == "부산"
    assert provider.calls == 0


def test_keyword_hit_in_tags():
    client = _Client(region="서울")
    resolver = _resolver(_Provider(_video(tags=["vlog", "강릉여행", "바다"])), client)
    assert resolver.resolve("vid1", "주말 브이로그") == "강릉"
    assert client.calls == []


def test_keyword_hit_in_description():
    client = _Client(region="서울")
    resolver = _resolver(_Provider(_video(description="이번엔 서귀포 바다를 다녀왔어요")), client)
    assert resolver.resolve("vid1", "주말 브이로그") == "제주"
    assert client.calls == []


def test_exaone_fallback_accepted_when_known_region():
    client = _Client(region="여수시")
    resolver = _resolver(_Provider(_video(description="낭만 포차 거리와 밤바다" * 200)), client)
    assert resolver.resolve("vid1", "밤바다 브이로그") == "여수"
    call = client.calls[0]
    assert call["options"] == {"temperature": 0}
    assert call["format_schema"]["properties"]["region"]["type"] == ["string", "null"]
    assert "Channel: 여행채널" in call["messages"][1]["content"]
    assert len(call["messages"][1]["content"]) < 1700


def test_exaone_answer_rejected_when_not_known_region():
    for answer in ("도쿄", "Somewhere nice", None):
        assert _resolver(_Provider(_video()), _Client(region=answer)).resolve("vid1", "브이로그") is None
    assert _resolver(_Provider(_video()), _Client(raw="not json")).resolve("vid1", "브이로그") is None


def test_provider_errors_return_none():
    youtube_down = _Provider(error=AppError("YOUTUBE_QUOTA_EXCEEDED", "quota", 429))
    assert _resolver(youtube_down, _Client(region="부산")).resolve("vid1", "브이로그") is None

    ollama_down = _Client(error=AppError("OLLAMA_NETWORK_ERROR", "down", 502))
    assert _resolver(_Provider(_video()), ollama_down).resolve("vid1", "브이로그") is None

    def broken_client():
        raise AppError("EXAONE_BASE_URL_NOT_CONFIGURED", "no url", 503)

    resolver = YouTubeRegionResolver(lambda: _Provider(_video()), broken_client, "exaone")
    assert resolver.resolve("vid1", "브이로그") is None


def test_exaone_skipped_without_model():
    client = _Client(region="부산")
    assert _resolver(_Provider(_video()), client, model="").resolve("vid1", "브이로그") is None
    assert client.calls == []
