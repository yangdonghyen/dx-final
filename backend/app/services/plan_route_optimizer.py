"""Deterministic, same-slot place swaps that shorten each day's route.

The model chooses which verified places to visit and when.  This module only
moves those places between slots the model already made (sight with sight,
restaurant with restaurant, cafe with cafe) or puts an unused verified
restaurant/cafe into a meal or cafe slot, when that shortens the straight-line
route of the itinerary.  Slot times never change, so meal times, day starts
and day ends stay exactly as drafted.

Straight-line distance between stored coordinates is used only when no real
route metric is available.  It is never turned into a travel time.  When the
caller supplies a route-duration metric, every leg being compared must have a
provider fact; an UNKNOWN leg makes that proposed move ineligible.

A move is rejected when the place's verified opening hours exclude the slot,
when the place is a dated event, or when it would make the longest leg of the
plan longer.  Anchors and other fixed places are never moved.
"""

from __future__ import annotations

from datetime import time

from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.place_temporal_validation import is_event_candidate, opening_hours_match
from app.services.plan_quality_rules import distance_meters, is_cafe, is_restaurant

# A move must shorten the plan's total straight-line route by at least this much.
MIN_GAIN_METERS = 500
MAX_MOVES = 30
# A meal this far (straight line) from both of its neighbouring stops is reported.
FAR_MEAL_METERS = 5000


def role(place) -> str:
    if is_restaurant(place):
        return "restaurant"
    if is_cafe(place):
        return "cafe"
    return "sight"


def _clock(value):
    try:
        return time.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _located(day, places):
    rows = [item for item in day.items if item.place_id in places and _clock(item.start_time) is not None]
    rows.sort(key=lambda item: (_clock(item.start_time), item.sequence))
    return [item for item in rows if distance_meters(places[item.place_id], places[item.place_id]) is not None]


def route_legs(days, places):
    """[(visit_date, from_place_id, to_place_id, meters)] in time order per day."""
    legs = []
    for day in days:
        located = _located(day, places)
        for previous, current in zip(located, located[1:]):
            legs.append((day.visit_date, previous.place_id, current.place_id,
                         distance_meters(places[previous.place_id], places[current.place_id])))
    return legs


def route_length(days, places):
    meters = [leg[3] for leg in route_legs(days, places)]
    return sum(meters), max(meters, default=0.0)


def route_metric_length(days, places, metric):
    """Return total/longest verified metric, or None when any leg is UNKNOWN.

    ``metric`` is intentionally supplied by the generation service so this
    pure optimiser neither knows nor calls an external provider.  A value is
    useful only when it is a strictly positive numeric route fact.
    """
    values = []
    for day in days:
        located = _located(day, places)
        for previous, current in zip(located, located[1:]):
            value = metric(places[previous.place_id], places[current.place_id])
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                return None
            values.append(value)
    return sum(values), max(values, default=0.0)


def _fits(place, visit_date, item) -> bool:
    if is_event_candidate(place):
        return False
    return opening_hours_match(place, visit_date, _clock(item.start_time), _clock(item.end_time)) is not False


def _put(item, place_id, place):
    return PlanDraftItem(item.sequence, item.item_type, place.name, place_id, item.start_time, item.end_time, item.recommendation_reason)


def optimize_routes(
    draft: GeneratedPlanDraft,
    places: dict,
    fixed_ids: set[int],
    route_metric=None,
    minimum_gain: float = MIN_GAIN_METERS,
    gain_key: str = "gain_m",
):
    """Return (new draft, moves).  The input draft is not modified."""
    days = [PlanDraftDay(day.visit_date, list(day.items)) for day in draft.days]
    used = {item.place_id for day in days for item in day.items if item.place_id is not None}
    unused = [place_id for place_id in places if place_id not in used and role(places[place_id]) in {"restaurant", "cafe"}]
    moves = []

    def movable_slots():
        return [
            (day_index, item_index)
            for day_index, day in enumerate(days)
            for item_index, item in enumerate(day.items)
            if item.place_id in places and item.place_id not in fixed_ids and not is_event_candidate(places[item.place_id])
        ]

    for _ in range(MAX_MOVES):
        current_metric = route_metric_length(days, places, route_metric) if route_metric else route_length(days, places)
        if current_metric is None:
            break
        total, longest = current_metric
        best = None
        slots = movable_slots()
        for position, (day_a, index_a) in enumerate(slots):
            item_a = days[day_a].items[index_a]
            place_a = places[item_a.place_id]
            for day_b, index_b in slots[position + 1:]:
                item_b = days[day_b].items[index_b]
                place_b = places[item_b.place_id]
                if role(place_a) != role(place_b):
                    continue
                if not (_fits(place_b, days[day_a].visit_date, item_a) and _fits(place_a, days[day_b].visit_date, item_b)):
                    continue
                days[day_a].items[index_a], days[day_b].items[index_b] = _put(item_a, item_b.place_id, place_b), _put(item_b, item_a.place_id, place_a)
                new_metric = route_metric_length(days, places, route_metric) if route_metric else route_length(days, places)
                days[day_a].items[index_a], days[day_b].items[index_b] = item_a, item_b
                if new_metric is None:
                    continue
                new_total, new_longest = new_metric
                gain = total - new_total
                if gain >= minimum_gain and new_longest <= longest and (best is None or gain > best[0]):
                    best = (gain, "swap", (day_a, index_a, item_b.place_id), (day_b, index_b, item_a.place_id))
            if role(place_a) in {"restaurant", "cafe"}:
                for place_id in unused:
                    candidate = places[place_id]
                    if role(candidate) != role(place_a) or not _fits(candidate, days[day_a].visit_date, item_a):
                        continue
                    days[day_a].items[index_a] = _put(item_a, place_id, candidate)
                    new_metric = route_metric_length(days, places, route_metric) if route_metric else route_length(days, places)
                    days[day_a].items[index_a] = item_a
                    if new_metric is None:
                        continue
                    new_total, new_longest = new_metric
                    gain = total - new_total
                    if gain >= minimum_gain and new_longest <= longest and (best is None or gain > best[0]):
                        best = (gain, "replace", (day_a, index_a, place_id), None)
        if best is None:
            break
        gain, kind, first, second = best
        for change in (first, second):
            if change is None:
                continue
            day_index, item_index, place_id = change
            old = days[day_index].items[item_index]
            if kind == "replace":
                unused.remove(place_id)
                unused.append(old.place_id)
            moves.append({"kind": kind, "visit_date": days[day_index].visit_date.isoformat(), "sequence": old.sequence,
                          "from_place_id": old.place_id, "to_place_id": place_id, gain_key: round(gain)})
            days[day_index].items[item_index] = _put(old, place_id, places[place_id])
    return GeneratedPlanDraft(days=days), moves


def far_meals(draft: GeneratedPlanDraft, places: dict):
    """Meal stops farther than FAR_MEAL_METERS from every neighbouring stop."""
    found = []
    for day in draft.days:
        located = _located(day, places)
        for index, item in enumerate(located):
            if not is_restaurant(places[item.place_id]):
                continue
            neighbours = [located[i] for i in (index - 1, index + 1) if 0 <= i < len(located)]
            gaps = [distance_meters(places[item.place_id], places[other.place_id]) for other in neighbours]
            if gaps and min(gaps) > FAR_MEAL_METERS:
                found.append({"visit_date": day.visit_date.isoformat(), "sequence": item.sequence,
                              "place_id": item.place_id, "nearest_stop_m": round(min(gaps))})
    return found


# Senior rest (Phase 3C): a sight visit at least this long gets a rest break at
# its end, taken from the visit's own time (no slot moves, no new place).
REST_BREAK_MINUTES = 30
REST_AFTER_MINUTES_GENTLE = 90
REST_AFTER_MINUTES_DEFAULT = 150
REST_REASON = "휴식 선호에 맞춰 서버가 직전 방문 시간 일부를 휴식으로 배정했습니다. 휴식 시설은 확인되지 않았습니다."


def rest_policy(preferences: dict | None):
    """(visit minutes that earn a break, breaks per day) from stated preferences only."""
    preferences = preferences or {}
    if preferences.get("rest_frequency") == "LOW":
        return None, 0
    gentle = (preferences.get("rest_frequency") == "HIGH" or preferences.get("travel_style") == "SLOW"
              or preferences.get("walking_tolerance") in {"VERY_LOW", "LOW"})
    return (REST_AFTER_MINUTES_GENTLE if gentle else REST_AFTER_MINUTES_DEFAULT,
            2 if preferences.get("rest_frequency") == "HIGH" else 1)


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def insert_rest_breaks(draft: GeneratedPlanDraft, places: dict, fixed_ids: set[int], preferences: dict | None):
    """Return (new draft, inserted).  Days that already have a REST are left alone,
    as are anchors and visits that would drop below an hour."""
    threshold, per_day = rest_policy(preferences)
    days, inserted = [], []
    for day in draft.days:
        items = list(day.items)
        if threshold is None or any(item.item_type == "REST" for item in items):
            days.append(PlanDraftDay(day.visit_date, items))
            continue
        visits = []
        for index, item in enumerate(items):
            start, end = _clock(item.start_time), _clock(item.end_time)
            place = places.get(item.place_id)
            if (place is None or item.place_id in fixed_ids or role(place) != "sight" or start is None or end is None):
                continue
            length = _minutes(end) - _minutes(start)
            if length >= threshold and length - REST_BREAK_MINUTES >= 60:
                # A break between two sights is worth more than one before a meal or the day's end.
                following = [entry for entry in items if _clock(entry.start_time) and _clock(entry.start_time) >= end]
                following.sort(key=lambda entry: _clock(entry.start_time))
                before_sight = bool(following) and following[0].place_id in places and role(places[following[0].place_id]) == "sight"
                visits.append((before_sight, length, index))
        for *_, index in sorted(visits, reverse=True)[:per_day]:
            item = items[index]
            split = _minutes(_clock(item.end_time)) - REST_BREAK_MINUTES
            split_text = f"{split // 60:02d}:{split % 60:02d}"
            items[index] = PlanDraftItem(item.sequence, item.item_type, item.title, item.place_id, item.start_time, split_text, item.recommendation_reason)
            items.append(PlanDraftItem(0, "REST", "휴식", None, split_text, item.end_time, REST_REASON))
            inserted.append({"visit_date": day.visit_date.isoformat(), "after_place_id": item.place_id, "start": split_text, "end": item.end_time})
        if visits:
            items.sort(key=lambda entry: (_clock(entry.start_time) or time(0), entry.item_type == "REST"))
            items = [PlanDraftItem(number, entry.item_type, entry.title, entry.place_id, entry.start_time, entry.end_time, entry.recommendation_reason)
                     for number, entry in enumerate(items, start=1)]
        days.append(PlanDraftDay(day.visit_date, items))
    return GeneratedPlanDraft(days=days), inserted
