"""Resolve a saved YouTube discovery's Korean travel region from video metadata.

Order: keyword match over the title, tags and description, then a short
EXAONE call whose answer is accepted only when it names a known region.
"""

import json
from typing import Callable

from app.core.exceptions import AppError
from app.services.external.ai.ollama_client import OllamaClient
from app.services.external.content.provider import VideoMetadata
from app.services.external.place.region_resolver import normalize_administrative_name
from app.services.youtube_destination_resolver import YouTubeDestinationResolver

DESCRIPTION_LIMIT = 1500
TAGS_LIMIT = 40

_REGION_SCHEMA = {
    "type": "object",
    "properties": {"region": {"type": ["string", "null"]}},
    "required": ["region"],
}


class YouTubeRegionResolver:
    def __init__(
        self,
        content_provider_factory: Callable[[], object] | None = None,
        client_factory: Callable[[], OllamaClient] | None = None,
        model: str | None = None,
        keyword_resolver: YouTubeDestinationResolver | None = None,
    ):
        self.content_provider_factory = content_provider_factory
        self.client_factory = client_factory
        self.model = (model or "").strip()
        self.keywords = keyword_resolver or YouTubeDestinationResolver()

    @classmethod
    def from_settings(cls, settings=None) -> "YouTubeRegionResolver":
        from app.core.config import get_settings
        from app.services.external.factory import get_content_provider

        settings = settings or get_settings()
        return cls(
            content_provider_factory=lambda: get_content_provider(settings),
            client_factory=lambda: OllamaClient(settings.exaone_base_url, settings.ai_api_timeout_seconds),
            model=settings.exaone_model,
        )

    def known_region(self, value) -> str | None:
        """Map a free-text answer onto a known region, or None. Never invents one."""
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        candidates = {text, normalize_administrative_name(text)}
        for destination, aliases in YouTubeDestinationResolver._DESTINATIONS.items():
            names = {destination, *aliases}
            if candidates & names:
                return destination
        return None

    def _keyword_region(self, metadata: VideoMetadata) -> str | None:
        for text in (metadata.title, " ".join(metadata.tags or []), metadata.description):
            region = self.keywords.resolve(text)
            if region is not None:
                return region
        return None

    def _exaone_region(self, metadata: VideoMetadata) -> str | None:
        if self.client_factory is None or not self.model:
            return None
        known = ", ".join(YouTubeDestinationResolver._DESTINATIONS)
        tags = ", ".join((metadata.tags or [])[:TAGS_LIMIT]) or "-"
        description = (metadata.description or "")[:DESCRIPTION_LIMIT] or "-"
        system_prompt = (
            "You identify the single primary Korean travel region of a YouTube travel video. "
            f"Answer with one of these regions only: {known}. "
            "If the video is not clearly about exactly one of them, answer null. "
            "Never guess. Return only the required JSON."
        )
        user_prompt = (
            f"Title: {metadata.title}\n"
            f"Channel: {metadata.channel_title}\n"
            f"Tags: {tags}\n"
            f"Description:\n{description}"
        )
        client = self.client_factory()
        response = client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format_schema=_REGION_SCHEMA,
            options={"temperature": 0},
        )
        try:
            content = response["message"]["content"]
            region = json.loads(content)["region"] if isinstance(content, str) else None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return self.known_region(region)

    def resolve(self, video_id: str | None, title: str | None = None) -> str | None:
        region = self.keywords.resolve(title)
        if region is not None:
            return region
        if not video_id or self.content_provider_factory is None:
            return None
        stage = "youtube"
        try:
            metadata = self.content_provider_factory().get_video(video_id)
            region = self._keyword_region(metadata)
            if region is not None:
                return region
            stage = "exaone"
            region = self._exaone_region(metadata)
            print("[YouTube Region]", f"video_id={video_id}", f"exaone_region={region}")
            return region
        except AppError as error:
            print("[YouTube Region]", f"video_id={video_id}", f"{stage} failed code={error.code}")
            return None
        except Exception as error:  # never let region lookup break a save
            print("[YouTube Region]", f"video_id={video_id}", f"{stage} failed error={type(error).__name__}")
            return None
