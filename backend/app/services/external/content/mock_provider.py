from pathlib import Path

from app.core.exceptions import AppError
from app.services.external.mock_data import load_mock_collection
from app.services.external.content.provider import VideoMetadata


class MockContentProvider:
    """Local fixture-backed stand-in for a future YouTube provider."""
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir

    def get_video(self, video_id: str) -> VideoMetadata:
        if not isinstance(video_id, str) or not video_id.strip():
            raise AppError("INVALID_PROVIDER_INPUT", "video_id is required", 400)
        videos = load_mock_collection("youtube.json", "videos", {"video_id", "title", "description", "tags", "channel_id", "channel_title"}, self.data_dir)
        for video in videos:
            if video["video_id"] == video_id:
                tags = video["tags"]
                if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
                    raise AppError("EXTERNAL_PROVIDER_ERROR", "Mock data is invalid", 500)
                return VideoMetadata(**video)
        raise AppError("PROVIDER_NOT_FOUND", "Video was not found", 404)
