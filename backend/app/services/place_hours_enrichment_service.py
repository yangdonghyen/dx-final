"""Conservative TourAPI opening-hours enrichment for already linked places.

The service deliberately does *not* try to identify a TourAPI record from a
Kakao name/address.  A wrong identity would be worse than no hours data.  It
only uses a ``tour_content_id`` that was linked by a trusted ingest path.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
import re

from app.core.exceptions import AppError


logger = logging.getLogger("uvicorn.error")

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_KOREAN_WEEKDAYS = {
    "월": "monday", "화": "tuesday", "수": "wednesday", "목": "thursday",
    "금": "friday", "토": "saturday", "일": "sunday",
}
_RANGE = re.compile(r"(?P<open>[0-2]?\d:[0-5]\d)\s*(?:~|[-–])\s*(?P<close>[0-2]?\d:[0-5]\d)")
_CLOSED_DAY = re.compile(r"(?:매주\s*)?(?P<day>[월화수목금토일])(?:요일)?\s*(?:휴무|쉼)")


def _clock(value: str) -> str | None:
    try:
        hour, minute = (int(part) for part in value.split(":"))
    except (AttributeError, ValueError):
        return None
    return f"{hour:02d}:{minute:02d}" if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def _strict_schedule(operating_hours: str | None, closed_days: str | None) -> dict | None:
    """Parse only an explicit daily range; all other source text stays PARTIAL.

    TourAPI's fields are free text.  Treating a bare ``09:00~18:00`` as every
    day would invent a weekly schedule, so this accepts a range only when the
    source explicitly says ``매일`` or ``연중무휴``.  A named regular closure is
    represented explicitly and is therefore safe to reject.
    """
    raw = (operating_hours or "").strip()
    if not raw or not ("매일" in raw or "연중무휴" in raw):
        return None
    match = _RANGE.search(raw)
    if match is None:
        return None
    opened, closed = _clock(match.group("open")), _clock(match.group("close"))
    if opened is None or closed is None or closed < opened:
        return None
    schedule = {day: {"open": opened, "close": closed} for day in _WEEKDAYS}
    closure = _CLOSED_DAY.search((closed_days or "").strip())
    if closure is not None:
        schedule[_KOREAN_WEEKDAYS[closure.group("day")]] = {"closed": True}
    return schedule


def tour_hours_snapshot(detail: dict, checked_at: datetime) -> tuple[dict, str, str | None]:
    """Return JSON-safe source metadata, status, and unmodified closure text."""
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=UTC)
    raw_hours = detail.get("operating_hours") if isinstance(detail, dict) else None
    raw_closed_days = detail.get("rest_date") if isinstance(detail, dict) else None
    schedule = _strict_schedule(raw_hours, raw_closed_days)
    snapshot = {
        "source": "TOUR_API",
        "checked_at": checked_at.astimezone(UTC).isoformat(),
        "raw_operating_hours": raw_hours,
        "raw_closed_days": raw_closed_days,
    }
    if schedule is not None:
        snapshot["schedule"] = schedule
        return snapshot, "VERIFIED", raw_closed_days
    return snapshot, "PARTIAL", raw_closed_days


class PlaceHoursEnrichmentService:
    """Fetch official hours only for places with a trusted TourAPI identity."""

    def __init__(self, session, tour_provider, max_places: int = 8, now=None):
        self.session = session
        self.tour_provider = tour_provider
        self.max_places = max_places
        self.now = now or (lambda: datetime.now(UTC))

    def enrich(self, places) -> dict[str, int]:
        stats = {"linked": 0, "verified": 0, "partial": 0, "provider_error": 0, "budget_skipped": 0}
        if self.tour_provider is None:
            return stats
        for place in places:
            content_id = str(getattr(place, "tour_content_id", "") or "").strip()
            if not content_id:
                continue
            if stats["linked"] >= self.max_places:
                stats["budget_skipped"] += 1
                continue
            stats["linked"] += 1
            try:
                # No image endpoint: hours enrichment needs only common + intro.
                detail = self.tour_provider.get_place_detail(content_id, include_images=False)
            except AppError as error:
                stats["provider_error"] += 1
                logger.info("place_hours_enrichment outcome=provider_error code=%s", error.code)
                continue
            checked_at = self.now()
            snapshot, status, closed_days = tour_hours_snapshot(detail, checked_at)
            place.opening_hours = snapshot
            place.closed_days = closed_days
            place.verification_status = status
            place.details_updated_at = checked_at.replace(tzinfo=None)
            stats[status.casefold()] += 1
        if stats["linked"]:
            self.session.flush()
            logger.info(
                "place_hours_enrichment linked=%s verified=%s partial=%s provider_error=%s budget_skipped=%s",
                stats["linked"], stats["verified"], stats["partial"], stats["provider_error"], stats["budget_skipped"],
            )
        return stats
