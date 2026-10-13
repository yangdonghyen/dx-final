"""Travel time between scheduled places, stored only from route facts.

A leg is two consecutive timed place items on the same day, ordered by start
time (the same legs ``_validate_route_timing`` checks).  REST and FREE_TIME
items are not legs, so their time is never added to a travel value.
"""

from dataclasses import replace
from datetime import time
from math import ceil

ROUTE_MODES = {"WALK", "PUBLIC_TRANSIT", "CAR", "TAXI", "OTHER"}  # plan_items enum
EMPTY_TRAVEL = {
    "transport_mode_from_previous": None,
    "travel_minutes_from_previous": None,
    "travel_distance_meters_from_previous": None,
}


def travel_columns(estimate):
    """Columns for a leg; a missing or malformed fact stays NULL, never 0."""
    duration = getattr(estimate, "duration_seconds", None)
    mode = getattr(estimate, "mode", None)
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0 or mode not in ROUTE_MODES:
        return dict(EMPTY_TRAVEL)
    distance = getattr(estimate, "distance_meters", None)
    distance = distance if isinstance(distance, int) and not isinstance(distance, bool) and distance > 0 else None
    return {
        **EMPTY_TRAVEL,
        "transport_mode_from_previous": mode,
        "travel_minutes_from_previous": ceil(duration / 60),
        "travel_distance_meters_from_previous": distance,
    }


def stored_travel_columns(raw):
    """Re-read travel values saved in a preview proposal without changing them."""
    if not isinstance(raw, dict):
        return dict(EMPTY_TRAVEL)
    mode = raw.get("transport_mode_from_previous")
    minutes = raw.get("travel_minutes_from_previous")
    distance = raw.get("travel_distance_meters_from_previous")
    if mode not in ROUTE_MODES or isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        return dict(EMPTY_TRAVEL)
    distance = distance if isinstance(distance, int) and not isinstance(distance, bool) and distance > 0 else None
    return {**EMPTY_TRAVEL, "transport_mode_from_previous": mode, "travel_minutes_from_previous": minutes, "travel_distance_meters_from_previous": distance}


def route_legs(rows):
    """Yield (previous, current) pairs of timed place rows ``(item, start, end)``."""
    ordered = sorted((row for row in rows if row[0].place_id is not None and row[1] and row[2]), key=lambda row: row[1])
    return list(zip(ordered, ordered[1:]))


def travel_statuses(items):
    """KNOWN / UNKNOWN / NONE per stored item of one day, keyed by object id.

    NONE: not a place, or the day's first place (no leg before it).
    KNOWN: a stored route fact.  UNKNOWN: a leg exists but no fact was stored.
    """
    places = sorted(
        (item for item in items if item.place_id is not None),
        key=lambda item: (item.start_time is None, item.start_time or time.min, item.sequence_no),
    )
    first_id = id(places[0]) if places else None
    statuses = {}
    for item in items:
        if item.place_id is None or id(item) == first_id:
            statuses[id(item)] = "NONE"
        elif getattr(item, "travel_minutes_from_previous", None) is not None:
            statuses[id(item)] = "KNOWN"
        else:
            statuses[id(item)] = "UNKNOWN"
    return statuses


def travel_response_fields(item, status):
    return {
        "transport_mode_from_previous": getattr(item, "transport_mode_from_previous", None),
        "travel_minutes_from_previous": getattr(item, "travel_minutes_from_previous", None),
        "travel_distance_meters_from_previous": getattr(item, "travel_distance_meters_from_previous", None),
        "travel_status": status,
    }


# --- Automatic time shift for verified travel (Task 7.5k) -----------------
DAY_END = time(22, 0)
MEAL_WINDOWS = ((time(11, 30), time(13, 30)), (time(17, 30), time(19, 30)))


class TravelShiftConflict(Exception):
    """Shifting later items cannot make room for a verified leg."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _seconds(value):
    return value.hour * 3600 + value.minute * 60 + value.second


def _time(seconds):
    return time(seconds // 3600, seconds % 3600 // 60, seconds % 60)


def _text(value):
    return value.isoformat(timespec="minutes" if value.second == 0 else "seconds")


def _meal_window(start):
    return next((window for window in MEAL_WINDOWS if window[0] <= start <= window[1]), None)


def shift_day_for_travel(rows, travel_seconds):
    """Return ``rows`` with later items moved so every verified leg fits.

    ``rows`` are ``(item, start, end)`` tuples of one day; ``travel_seconds``
    returns the verified seconds between two place items, or ``None``.
    Only start/end move: durations, order, places and days never change.
    The time needed before a place is the previous place's end, plus the
    REST/FREE_TIME time scheduled between them, plus the travel itself, so a
    rest is never counted as travel.  An UNKNOWN leg adds nothing.
    """
    timed = sorted((index for index, row in enumerate(rows) if row[1] and row[2]), key=lambda index: rows[index][1])
    shifted = list(rows)
    shift = 0
    previous_place = None
    between = 0
    for index in timed:
        item, start, end = rows[index]
        new_start, new_end = _seconds(start) + shift, _seconds(end) + shift
        if item.place_id is not None:
            if previous_place is not None:
                previous_item, _, previous_end = shifted[previous_place]
                travel = travel_seconds(previous_item, item)
                if travel is not None:
                    travel_minutes = -(-travel // 60)
                    required = _seconds(previous_end) + between + travel_minutes * 60
                    if new_start < required:
                        delta = required - new_start
                        shift += delta
                        new_start += delta
                        new_end += delta
            previous_place = index
            between = 0
        elif previous_place is not None:
            between += new_end - new_start
        if new_start != _seconds(start):
            if new_end >= 24 * 3600 or new_end > _seconds(DAY_END):
                raise TravelShiftConflict(
                    f"Verified travel time pushes '{item.title}' past {_text(DAY_END)}"
                )
            window = _meal_window(start) if item.item_type == "MEAL" else None
            if window is not None and not window[0] <= _time(new_start) <= window[1]:
                raise TravelShiftConflict(
                    f"Verified travel time moves meal '{item.title}' outside its meal window"
                )
            moved_start, moved_end = _time(new_start), _time(new_end)
            shifted[index] = (
                replace(item, start_time=_text(moved_start), end_time=_text(moved_end)),
                moved_start,
                moved_end,
            )
    return shifted
