"""Phase 3A: safe repair of repeated places, missing-lunch repair, day balance
and candidate supply checks.  No Ollama, Kakao or database access."""

import json
from datetime import date, time
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.services.external.ai.exaone_plan_provider import ExaonePlanGenerationProvider
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_quality_rules import DayStop, PlanQualityRules, candidate_supply, review_plan


class Client:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        return {"message": {"content": self.answers.pop(0)}, "done_reason": "stop"}


def candidate(place_id, name, category, kind, anchor=False, hours=None, event=None):
    return {"place_id": place_id, "name": name, "category": category, "region": "부산광역시 수영구",
            "address": "부산광역시 수영구", "is_anchor": anchor, "activity_kind": kind,
            "opening_hours": hours, "event_start_date": event, "event_end_date": event}


SIGHT, FOOD = "NON_FOOD_ACTIVITY", "FOOD_OR_CAFE"
BEACH = candidate(1, "광안리해수욕장", "여행 > 관광,명소 > 해수욕장", SIGHT)
MUSEUM = candidate(2, "부산시립미술관", "문화,예술 > 미술관", SIGHT)
PARK = candidate(3, "이기대공원", "여행 > 공원", SIGHT)
LUNCH = candidate(4, "수영 국밥", "음식점 > 한식", FOOD)
DINNER = candidate(5, "민락 횟집", "음식점 > 한식 > 회", FOOD)


def item(sequence, item_type, place, start, end):
    return {"sequence": sequence, "item_type": item_type, "title": place["name"] if place else "휴식",
            "place_id": place["place_id"] if place else None, "start_time": start, "end_time": end}


def answer(*days):
    return json.dumps({"days": [{"visit_date": visit_date, "items": items} for visit_date, items in days]}, ensure_ascii=False)


def generate(client, places, end_date="2026-10-30"):
    provider = ExaonePlanGenerationProvider("http://127.0.0.1:11434", "exaone-test", 60, client)
    trip = {"destination": "부산", "start_date": "2026-10-29", "end_date": end_date}
    return provider, provider.generate_plan(trip, {}, [], ["FOOD"], {}, places)


def ids(draft):
    return [entry.place_id for day in draft.days for entry in day.items]


def times(draft):
    return [(entry.start_time, entry.end_time) for day in draft.days for entry in day.items]


def test_repeated_place_is_repaired_in_place_without_a_second_model_call():
    client = Client(answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30"), item(2, "MEAL", LUNCH, "12:00", "13:00")]),
        ("2026-10-30", [item(1, "PLACE", BEACH, "10:00", "11:30"), item(2, "MEAL", DINNER, "18:00", "19:00")]),
    ))

    provider, draft = generate(client, [BEACH, MUSEUM, LUNCH, DINNER])

    assert client.calls == 1
    assert ids(draft) == [1, 4, 2, 5]
    assert draft.days[1].items[0].title == "부산시립미술관" and draft.days[1].items[0].item_type == "PLACE"
    assert times(draft) == [("10:00", "11:30"), ("12:00", "13:00"), ("10:00", "11:30"), ("18:00", "19:00")]
    [call] = provider.call_diagnostics
    assert call["result"] == "repaired"
    assert call["repairs"][0]["replacement_place_id"] == 2
    assert call["repairs"][0]["reason"].startswith("duplicate_place_id:1;")


def test_repeat_without_a_same_kind_candidate_falls_back_to_the_ai_retry():
    # Only a restaurant is unused; a sight slot is never filled with a meal.
    repeated = answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
    )
    fixed = answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "MEAL", LUNCH, "12:00", "13:00")]),
    )
    client = Client(repeated, fixed)

    provider, draft = generate(client, [BEACH, LUNCH])

    assert client.calls == 2
    assert ids(draft) == [1, 4]
    first, second = provider.call_diagnostics
    assert first["result"] == "invalid" and first["validation_reason"].startswith("duplicate_place_id:1;")
    assert second["result"] == "valid"


def test_unrepairable_repeat_on_both_answers_is_still_rejected():
    repeated = answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
    )
    with pytest.raises(AppError) as error:
        generate(Client(repeated, repeated), [BEACH, LUNCH])
    assert error.value.code == "EXAONE_INVALID_RESPONSE"


def test_repeated_anchor_keeps_its_first_visit_and_unused_anchor_is_preferred():
    anchor = {**BEACH, "is_anchor": True}
    other_anchor = {**PARK, "is_anchor": True}
    client = Client(answer(
        ("2026-10-29", [item(1, "PLACE", anchor, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", anchor, "10:00", "11:30")]),
    ))

    _, draft = generate(client, [MUSEUM, anchor, other_anchor])

    assert ids(draft) == [1, 3]


def test_repair_never_uses_a_closed_or_dated_candidate():
    closed = candidate(6, "야간 전망대", "여행 > 관광,명소 > 전망대", SIGHT,
                       hours={"friday": {"open": "18:00", "close": "22:00"}})
    festival = candidate(7, "불꽃축제", "여행 > 축제", SIGHT, event="2026-11-07")
    client = Client(answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", BEACH, "10:00", "11:30")]),  # 2026-10-30 is a Friday
    ), answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", PARK, "10:00", "11:30")]),
    ))

    provider, draft = generate(client, [BEACH, closed, festival, PARK])

    # PARK is a valid unused sight, so the first answer is repaired with it.
    assert client.calls == 1 and ids(draft) == [1, 3]
    _, draft = generate(Client(answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
    ), answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:30")]),
        ("2026-10-30", [item(1, "PLACE", closed, "18:30", "19:30")]),
    )), [BEACH, closed, festival])
    # Neither the closed viewpoint nor the dated festival is used: AI retry instead.
    assert ids(draft) == [1, 6]


def test_repeat_inside_one_day_keeps_the_slot_times():
    client = Client(answer(
        ("2026-10-29", [item(1, "PLACE", BEACH, "10:00", "11:00"), item(2, "PLACE", BEACH, "14:00", "15:00")]),
    ))
    _, draft = generate(client, [BEACH, MUSEUM], end_date="2026-10-29")
    assert ids(draft) == [1, 2] and times(draft) == [("10:00", "11:00"), ("14:00", "15:00")]


# ---- missing lunch -----------------------------------------------------------

def place(place_id, name, category, hours=None):
    return SimpleNamespace(place_id=place_id, name=name, category=category, latitude=35.15, longitude=129.11,
                           address=None, verification_status="VERIFIED" if hours else "UNVERIFIED",
                           opening_hours=hours, event_start_date=None, event_end_date=None)


def service():
    generation = PlanGenerationService(None, None)
    generation._quality_rules = PlanQualityRules()
    return generation


def draft_day(*items):
    return GeneratedPlanDraft(days=[PlanDraftDay(date(2026, 10, 29), [PlanDraftItem(*row, "") for row in items])])


def prepare(places, draft, anchors=()):
    candidates = {row.place_id: row for row in places}
    trip = SimpleNamespace(trip_id=68)
    return service()._prepare_draft(draft, candidates, set(anchors), trip)


SIGHTS = [place(1, "광안리해수욕장", "여행 > 관광,명소 > 해수욕장"), place(2, "사진관", "문화,예술 > 사진관"),
          place(3, "테마거리", "여행 > 관광,명소 > 테마거리")]
RESTAURANT = place(4, "수영 국밥", "음식점 > 한식")
SUPPER = place(5, "민락 횟집", "음식점 > 한식")


def busan_day_one():
    return draft_day(
        (1, "PLACE", "광안리해수욕장", 1, "09:00", "12:00"), (2, "PLACE", "사진관", 2, "12:30", "13:30"),
        (3, "PLACE", "테마거리", 3, "14:00", "16:00"), (4, "MEAL", "민락 횟집", 5, "17:30", "19:00"))


def test_missing_lunch_takes_an_unused_restaurant_in_the_lunch_slot():
    result = prepare(SIGHTS + [RESTAURANT, SUPPER], busan_day_one())
    lunch = result.days[0].items[1]
    assert (lunch.place_id, lunch.item_type, lunch.start_time, lunch.end_time) == (4, "MEAL", "12:30", "13:30")
    assert [entry.place_id for entry in result.days[0].items] == [1, 4, 3, 5]


def test_missing_lunch_stays_missing_without_an_unused_restaurant():
    result = prepare(SIGHTS + [SUPPER], busan_day_one())
    assert [entry.place_id for entry in result.days[0].items] == [1, 2, 3, 5]


def test_missing_lunch_never_moves_an_anchor_or_a_closed_restaurant():
    closed = place(4, "저녁만 하는 집", "음식점 > 한식", hours={"thursday": {"open": "17:00", "close": "22:00"}})
    assert [e.place_id for e in prepare(SIGHTS + [closed, SUPPER], busan_day_one()).days[0].items] == [1, 2, 3, 5]
    # The anchor at 12:30 stays; the next sight starting inside the lunch window (14:00) takes lunch.
    result = prepare(SIGHTS + [RESTAURANT, SUPPER], busan_day_one(), anchors={2}).days[0].items
    assert [e.place_id for e in result] == [1, 2, 4, 5] and result[2].start_time == "14:00"


def test_missing_lunch_prefers_an_empty_slot_over_a_sight():
    draft = draft_day((1, "PLACE", "광안리해수욕장", 1, "09:00", "11:30"), (2, "FREE_TIME", "자유 시간", None, "12:00", "13:00"),
                      (3, "PLACE", "사진관", 2, "13:00", "14:00"), (4, "PLACE", "테마거리", 3, "14:30", "16:00"),
                      (5, "MEAL", "민락 횟집", 5, "17:30", "19:00"))
    assert [e.place_id for e in prepare(SIGHTS + [RESTAURANT, SUPPER], draft).days[0].items] == [1, 4, 2, 3, 5]


# ---- day balance and supply --------------------------------------------------

def stop(sequence, item_type, start, end, at=None):
    return DayStop(sequence, item_type, time.fromisoformat(start), time.fromisoformat(end), at)


def test_four_sights_in_a_row_without_a_break_are_flagged():
    day = [stop(i, "PLACE", f"{9 + i}:00", f"{9 + i}:50", SIGHTS[i % 3]) for i in range(1, 5)]
    assert "CONSECUTIVE_SIGHTS" in [f.code for f in review_plan([("1일차", day)], PlanQualityRules())]


def test_uneven_full_days_are_flagged_but_a_short_arrival_day_is_not():
    busy = [stop(1, "PLACE", "09:00", "12:00", SIGHTS[0]), stop(2, "MEAL", "12:30", "13:30", RESTAURANT),
            stop(3, "PLACE", "14:00", "17:00", SIGHTS[1]), stop(4, "MEAL", "18:00", "19:00", SUPPER)]
    light = [stop(1, "FREE_TIME", "09:00", "12:00"), stop(2, "MEAL", "12:30", "13:30", RESTAURANT),
             stop(3, "PLACE", "14:00", "15:00", SIGHTS[2]), stop(4, "MEAL", "18:00", "19:00", SUPPER)]
    arrival = [stop(1, "PLACE", "16:00", "17:00", SIGHTS[2]), stop(2, "MEAL", "18:00", "19:00", SUPPER)]
    rules = PlanQualityRules()
    assert [f.day for f in review_plan([("1일차", busy), ("2일차", light)], rules) if f.code == "UNEVEN_DAYS"] == ["2일차"]
    assert not [f for f in review_plan([("1일차", arrival), ("2일차", busy)], rules) if f.code == "UNEVEN_DAYS"]


def located(place_id, category, latitude, longitude):
    return SimpleNamespace(place_id=place_id, name=str(place_id), category=category, latitude=latitude, longitude=longitude)


def test_candidate_supply_reports_too_few_sights_and_a_single_area():
    jeju = [located(1, "여행 > 관광,명소 > 드라이브코스", 33.47, 126.36)] + [located(i, "음식점 > 한식", 33.47, 126.36) for i in range(2, 10)]
    supply = candidate_supply(jeju, trip_days=3)
    assert (supply["sights"], supply["restaurants"], supply["problems"][0]) == (1, 8, "SIGHTS_FEWER_THAN_DAYS")

    # A beach, a square and a theme street on one shore: enough sights, one area.
    shore = [located(i, category, 35.153 + i * 0.001, 129.119) for i, category in enumerate(
        ["여행 > 관광,명소 > 해수욕장", "여행 > 관광,명소 > 광장", "여행 > 관광,명소 > 테마거리", "여행 > 도보여행"])]
    supply = candidate_supply(shore, trip_days=2)
    # No restaurants either (Phase 3B): lunch and dinner slots are reported too.
    assert supply["sights"] == 4 and supply["areas"] == 1 and supply["problems"] == ["SINGLE_AREA", "RESTAURANTS_FEWER_THAN_MEALS"]
    assert supply["shortfall"] == {"sights": 0, "restaurants": 4, "areas": 1}
    spread = shore + [located(9, "문화,예술 > 미술관", 35.10, 129.03)] + [located(20 + i, "음식점 > 한식", 35.10, 129.03) for i in range(4)]
    assert candidate_supply(spread, trip_days=2)["problems"] == []
