"""Verified official-hours evidence without provider-specific identity guesses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
import re


@dataclass(frozen=True)
class OfficialPlaceHoursEvidence:
    source_url: str
    source_name: str
    checked_at: datetime
    applies_to: str
    official_name: str
    official_address: str
    latitude: float
    longitude: float
    facility_type: str
    seasonal: list[dict]
    closed_days: str | None = None


def _name(value) -> str:
    return "".join(char for char in str(value or "").casefold() if char.isalnum())


def _address_tokens(value) -> set[str]:
    text = str(value or "").replace("광역시", "").replace("특별시", "")
    return {token.casefold() for token in re.findall(r"[가-힣A-Za-z]+|\d+(?:-\d+)?", text) if len(token) >= 2 or token[0].isdigit()}


def _distance_meters(place, evidence) -> float | None:
    try:
        lat_a, lng_a = float(place.latitude), float(place.longitude)
    except (TypeError, ValueError):
        return None
    lat_b, lng_b = evidence.latitude, evidence.longitude
    delta_lat, delta_lng = radians(lat_b - lat_a), radians(lng_b - lng_a)
    value = sin(delta_lat / 2) ** 2 + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(delta_lng / 2) ** 2
    return 6371000 * 2 * asin(sqrt(value))


def official_evidence_matches(place, evidence: OfficialPlaceHoursEvidence) -> bool:
    """Require name, strong address, type and a strict 150m coordinate match."""
    if _name(place.name) != _name(evidence.official_name):
        return False
    shared = _address_tokens(getattr(place, "address", None)) & _address_tokens(evidence.official_address)
    generic_words = {"si", "gu", "dong", "ro", "gil", "street", "road"}
    specific_words = [token for token in shared if not token[0].isdigit() and token not in generic_words]
    if not any(token[0].isdigit() for token in shared) or len(specific_words) < 2:
        return False
    category = str(getattr(place, "category", "") or "").casefold()
    if evidence.facility_type == "TOURIST_ATTRACTION" and not any(token in category for token in ("관광", "문화", "명소", "at4", "ct1")):
        return False
    if evidence.facility_type == "RESTAURANT" and not any(token in category for token in ("음식", "식당", "맛집", "fd6")):
        return False
    distance = _distance_meters(place, evidence)
    return distance is not None and distance <= 150


def apply_official_hours_evidence(place, evidence: OfficialPlaceHoursEvidence) -> bool:
    """Attach only a fully verified source snapshot; caller owns persistence."""
    if not official_evidence_matches(place, evidence):
        return False
    checked_at = evidence.checked_at if evidence.checked_at.tzinfo else evidence.checked_at.replace(tzinfo=UTC)
    place.opening_hours = {
        "source": "OFFICIAL_PLACE_SOURCE",
        "source_name": evidence.source_name,
        "source_url": evidence.source_url,
        "checked_at": checked_at.astimezone(UTC).isoformat(),
        "applies_to": evidence.applies_to,
        "schedule": {"seasonal": evidence.seasonal},
    }
    place.closed_days = evidence.closed_days
    place.verification_status = "VERIFIED"
    place.details_updated_at = checked_at.replace(tzinfo=None)
    return True
