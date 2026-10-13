"""Conservative opening-hours repair using only AI-created FREE_TIME."""

from __future__ import annotations

from dataclasses import replace
from datetime import time

from app.services.place_temporal_validation import opening_hours_for_date, opening_hours_match


SLOW_MIN_FREE_MINUTES = 60
DEFAULT_MIN_FREE_MINUTES = 30


def _seconds(value: time) -> int:
    return value.hour * 3600 + value.minute * 60 + value.second


def _clock(seconds: int) -> time:
    return time(seconds // 3600, seconds % 3600 // 60, seconds % 60)


def _text(value: time) -> str:
    return value.isoformat(timespec="minutes")


def _minimum_free_seconds(preferences: dict) -> int:
    gentle = preferences.get("travel_style") == "SLOW" or preferences.get("rest_frequency") == "HIGH"
    return (SLOW_MIN_FREE_MINUTES if gentle else DEFAULT_MIN_FREE_MINUTES) * 60


def adjust_day_for_opening_hours(rows, visit_date, places, anchor_ids, preferences):
    """Move a non-anchor visit earlier by shrinking its immediately prior FREE_TIME.

    This is intentionally narrower than general scheduling: REST, MEAL, anchors
    and all non-FREE_TIME items are untouched.  It returns the unchanged rows
    plus an unresolved record if a verified conflict cannot be repaired.
    """
    changed, adjustments, unresolved = list(rows), [], []
    minimum_free = _minimum_free_seconds(preferences or {})
    for index, (item, start, end) in enumerate(list(changed)):
        place = places.get(item.place_id) if item.place_id is not None else None
        if place is None or opening_hours_match(place, visit_date, start, end) is not False:
            continue
        row = opening_hours_for_date(place, visit_date)
        close = row.get("close") if isinstance(row, dict) else None
        try:
            close_time = time.fromisoformat(close)
        except (TypeError, ValueError):
            unresolved.append({"place_id": item.place_id, "reason": "UNSUPPORTED_HOURS"})
            continue
        if item.place_id in anchor_ids or end is None or end <= close_time:
            unresolved.append({"place_id": item.place_id, "reason": "ANCHOR_OR_UNSUPPORTED_CONFLICT"})
            continue
        needed = _seconds(end) - _seconds(close_time)
        free_index = next((candidate for candidate in range(index - 1, -1, -1) if changed[candidate][0].item_type == "FREE_TIME" and changed[candidate][0].place_id is None), None)
        if free_index is None:
            unresolved.append({"place_id": item.place_id, "reason": "NO_FLEXIBLE_FREE_TIME"})
            continue
        free_item, free_start, free_end = changed[free_index]
        if free_start is None or free_end is None or _seconds(free_end) - _seconds(free_start) - needed < minimum_free:
            unresolved.append({"place_id": item.place_id, "reason": "FREE_TIME_MINIMUM"})
            continue
        # Nothing between the selected flexible slot and the visit may overlap
        # after the move.  This prevents compressing a fixed meal/rest/anchor.
        if any(changed[row_index][2] and changed[row_index][2] > _clock(_seconds(start) - needed) for row_index in range(free_index + 1, index)):
            unresolved.append({"place_id": item.place_id, "reason": "FIXED_ITEM_BETWEEN"})
            continue
        new_free_end = _clock(_seconds(free_end) - needed)
        new_start, new_end = _clock(_seconds(start) - needed), _clock(_seconds(end) - needed)
        changed[free_index] = (replace(free_item, end_time=_text(new_free_end)), free_start, new_free_end)
        changed[index] = (replace(item, start_time=_text(new_start), end_time=_text(new_end), recommendation_reason=(item.recommendation_reason or "") + " [공식 운영시간에 맞춰 유동 자유 시간을 조정했습니다.]"), new_start, new_end)
        adjustments.append({"place_id": item.place_id, "minutes": needed // 60 if needed % 60 == 0 else needed / 60, "reason": "VERIFIED_CLOSING_TIME"})
    return changed, adjustments, unresolved
