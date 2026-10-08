from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit
import re

from app.core.exceptions import AppError
from app.repositories.trip_repository import TripRepository, TripSourceRepository
from app.schemas.trip import YouTubeSourceResponse


_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{1,255}$")


def extract_video_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppError("INVALID_YOUTUBE_URL", "YouTube URL or video ID is required", 400)
    value = value.strip()
    if _VIDEO_ID.fullmatch(value): return value
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            values = parse_qs(parsed.query).get("v", [])
            if len(values) == 1 and _VIDEO_ID.fullmatch(values[0]): return values[0]
        if parsed.path.startswith("/shorts/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 2 and _VIDEO_ID.fullmatch(parts[1]): return parts[1]
    if host == "youtu.be":
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) == 1 and _VIDEO_ID.fullmatch(parts[0]): return parts[0]
    raise AppError("INVALID_YOUTUBE_URL", "Invalid YouTube URL", 400)


class YouTubeSourceService:
    def __init__(self, session, content_provider):
        self.session = session
        self.trips = TripRepository(session)
        self.sources = TripSourceRepository(session)
        self.content_provider = content_provider

    def _owned_active_trip(self, user_id, trip_id):
        trip = self.trips.get(trip_id)
        if trip is None: raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED": raise AppError("TRIP_ARCHIVED", "Trip is archived", 400)
        return trip

    def add(self, user_id, trip_id, youtube_url):
        self._owned_active_trip(user_id, trip_id)
        video_id = extract_video_id(youtube_url)
        try:
            metadata = self.content_provider.get_video(video_id)
        except AppError as error:
            if error.code == "PROVIDER_NOT_FOUND": raise AppError("YOUTUBE_VIDEO_NOT_FOUND", "YouTube video not found", 404) from None
            raise
        fields = {"external_id": metadata.video_id, "source_url": youtube_url, "title": metadata.title, "description": metadata.description, "tags": metadata.tags, "channel_id": metadata.channel_id, "channel_title": metadata.channel_title, "metadata_collected_at": datetime.now(UTC).replace(tzinfo=None), "is_active": True}
        try:
            source = self.sources.get_by_external(trip_id, metadata.video_id)
            if source is None: source = self.sources.create(trip_id, **fields)
            else: source = self.sources.update(source, **fields)
            self.session.commit()
            return YouTubeSourceResponse(source_id=source.source_id, video_id=source.external_id, title=source.title, description=source.description, tags=source.tags or [])
        except Exception:
            self.session.rollback(); raise

    def deactivate(self, user_id, trip_id, source_id):
        self._owned_active_trip(user_id, trip_id)
        source = self.sources.get(source_id)
        if source is None or source.trip_id != trip_id: raise AppError("SOURCE_NOT_FOUND", "Source not found", 404)
        try:
            self.sources.update(source, is_active=False)
            self.session.commit()
        except Exception:
            self.session.rollback(); raise
