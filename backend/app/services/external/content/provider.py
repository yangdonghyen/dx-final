from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    description: str
    tags: list[str]
    channel_id: str
    channel_title: str
    thumbnail_url: str | None = None


class ContentProvider(Protocol):
    def get_video(self, video_id: str) -> VideoMetadata: ...
