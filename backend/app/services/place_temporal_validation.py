"""Conservative temporal checks for verified place metadata.

Opening-hours JSON uses weekday keys (English or Korean) mapped to an object
with ``open`` and ``close`` HH:MM strings. Unknown or unsupported metadata is
never guessed and therefore does not produce an hours assertion.
"""

from datetime import date, datetime, time


EVENT_KEYWORDS = ("축제", "불꽃축제", "페스티벌", "festival", "행사", "박람회")
WEEKDAYS = {
    "monday": 0, "mon": 0, "월요일": 0, "월": 0,
    "tuesday": 1, "tue": 1, "화요일": 1, "화": 1,
    "wednesday": 2, "wed": 2, "수요일": 2, "수": 2,
    "thursday": 3, "thu": 3, "목요일": 3, "목": 3,
    "friday": 4, "fri": 4, "금요일": 4, "금": 4,
    "saturday": 5, "sat": 5, "토요일": 5, "토": 5,
    "sunday": 6, "sun": 6, "일요일": 6, "일": 6,
}


def is_event_candidate(place) -> bool:
    name = str(getattr(place, "name", "") or "").casefold()
    category = str(getattr(place, "category", "") or "").casefold()
    return any(word in name or word in category for word in EVENT_KEYWORDS)


def _date_value(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def event_dates(place):
    start = _date_value(getattr(place, "event_start_date", None))
    end = _date_value(getattr(place, "event_end_date", None))
    return (start, end) if start is not None and end is not None and end >= start else None


def event_overlaps_trip(place, start_date: date, end_date: date) -> bool | None:
    dates = event_dates(place)
    if dates is None:
        return None
    return dates[0] <= end_date and dates[1] >= start_date


def verified_hours(place):
    hours = getattr(place, "opening_hours", None)
    if getattr(place, "verification_status", None) != "VERIFIED" or not isinstance(hours, dict):
        return None
    return hours


def _clock(value):
    if not isinstance(value, str):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def opening_hours_match(place, visit_date: date, start: time | None, end: time | None) -> bool | None:
    hours = verified_hours(place)
    if hours is None or start is None or end is None:
        return None
    day_row = next((value for key, value in hours.items() if WEEKDAYS.get(str(key).casefold()) == visit_date.weekday()), None)
    if not isinstance(day_row, dict):
        return None
    open_time, close_time = _clock(day_row.get("open")), _clock(day_row.get("close"))
    if open_time is None or close_time is None:
        return None
    return start >= open_time and end <= close_time and close_time >= open_time
