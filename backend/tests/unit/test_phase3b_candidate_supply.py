"""Phase 3B: candidate supply by pace, area and meal slots; conservative
replacement of a repeated place.  No Ollama, Kakao or database access."""

import json
import logging

import pytest

from app.core.exceptions import AppError
from app.services.external.ai.exaone_plan_provider import ExaonePlanGenerationProvider
from app.services.external.place.provider import PlaceCandidate
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_quality_rules import is_restaurant
from tests.unit.test_plan_generation_service import NearbyProvider, Place, service  # noqa: F401  (fixture)

SHORE = (37.500, 126.900)
FAR = (37.560, 126.990)  # about 10 km away


def sight(place_id, name, at=SHORE, offset=0.0):
    return Place(place_id, name, "여행 > 관광,명소", address=f"Seoul Jongno-gu {place_id}",
                 latitude=at[0] + offset, longitude=at[1], kakao_place_id=f"sight-{place_id}")


def restaurant(place_id, name):
    return Place(place_id, name, "음식점 > 한식", address=f"Seoul Jongno-gu {place_id}", kakao_place_id=f"food-{place_id}")


def cafe(place_id):
    return Place(place_id, f"카페 {place_id}", "음식점 > 카페", address=f"Seoul Jongno-gu {place_id}", kakao_place_id=f"cafe-{place_id}")


class SearchProvider(NearbyProvider):
    """Returns only what a test hands it, as a place search API would."""

    def __init__(self, results):
        super().__init__()
        self.results = results
        self.searches = []

    def search(self, query, region):
        self.searches.append(query)
        return self.results.get(query, [])


def found(external_id, name, category, at):
    return PlaceCandidate("KAKAO", external_id, name, category, f"Seoul Jongno-gu {external_id}", at[0], at[1], None, None)


def two_days(trip):
    trip.end_date = trip.start_date.replace(day=trip.start_date.day + 1)
    return trip


def test_targets_follow_pace_rest_and_food_focus():
    targets = PlanGenerationService._candidate_targets
    assert targets(2, {"travel_style": "SLOW"}) == {"sights": 4, "restaurants": 4, "areas": 2}
    assert targets(2, {"travel_style": "STANDARD"})["sights"] == 6
    assert targets(2, {"travel_style": "STANDARD", "rest_frequency": "HIGH"})["sights"] == 4
    assert targets(3, {"travel_style": "FOOD_FOCUSED"})["restaurants"] == 9
    assert targets(1, {})["areas"] == 1


def test_sights_are_interleaved_across_areas():
    shore = [sight(1, "해변", SHORE), sight(2, "광장", SHORE, 0.001), sight(3, "테마거리", SHORE, 0.002)]
    museum = sight(4, "미술관", FAR)
    ordered = PlanGenerationService._interleave_by_area(shore + [museum])
    assert [place.place_id for place in ordered] == [1, 4, 2, 3]


def test_pool_keeps_restaurants_for_every_meal_before_cafes(service):
    generator, session, _, _ = service
    trip = two_days(session.trips[1])
    sights = [sight(10 + i, f"관광 {i}", SHORE, i * 0.03) for i in range(8)]
    cafes = [cafe(30 + i) for i in range(8)]
    meals = [restaurant(50 + i, f"식당 {i}") for i in range(4)]

    pool = generator._balanced_candidate_pool(sights + cafes + meals, [], trip)

    assert sum(place.category == "음식점 > 한식" for place in pool) == 4
    assert len(pool) == 15


def test_enough_sights_in_one_area_still_search_for_another_area(service):
    generator, session, _, _ = service
    trip = two_days(session.trips[1])
    session.places = [sight(200 + i, f"광안리 {i}", SHORE, i * 0.001) for i in range(6)] + [restaurant(300 + i, f"식당 {i}") for i in range(4)]
    provider = SearchProvider({"관광지": [found("museum-1", "먼 미술관", "AT4 여행 > 관광,명소", FAR)]})
    generator.place_provider = provider

    pool = generator._candidate_places(trip, [], {"travel_style": "SLOW"})

    assert provider.searches[0] == "관광지"
    assert any(place.name == "먼 미술관" for place in pool)


def test_restaurants_are_searched_only_when_meal_slots_outnumber_them(service, caplog):
    generator, session, _, _ = service
    trip = two_days(session.trips[1])
    # Four cached places reach the general pool size, so only the meal check searches.
    session.places = [sight(200, "해변", SHORE), sight(201, "미술관", FAR), restaurant(300, "식당 하나"), cafe(400)]
    provider = SearchProvider({"맛집": [found(f"meal-{i}", f"검색 식당 {i}", "FD6 음식점 > 한식", SHORE) for i in range(3)]})
    generator.place_provider = provider

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        pool = generator._candidate_places(trip, [], {"travel_style": "SLOW"})

    assert "맛집" in provider.searches
    assert sum(is_restaurant(place) for place in pool) == 4
    assert "plan_candidate_meal_backfill" in caplog.text and "needed=4 cached=1 found=3" in caplog.text

    session.places = [sight(200, "해변", SHORE), sight(201, "미술관", FAR)] + [restaurant(300 + i, f"식당 {i}") for i in range(4)]
    provider.searches.clear()
    generator._candidate_places(trip, [], {"travel_style": "SLOW"})
    assert "맛집" not in provider.searches


def test_without_a_provider_the_shortfall_is_reported_not_invented(service, caplog):
    generator, session, _, _ = service
    trip = two_days(session.trips[1])
    generator.place_provider = None
    session.places = [sight(200 + i, f"광안리 {i}", SHORE, i * 0.001) for i in range(6)] + [restaurant(300, "식당"), restaurant(301, "식당2")]

    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        pool = generator._candidate_places(trip, [], {"travel_style": "SLOW"})

    assert {place.place_id for place in pool} == {200, 201, 202, 203, 204, 205, 300, 301}
    assert "problems=SINGLE_AREA,RESTAURANTS_FEWER_THAN_MEALS" in caplog.text
    assert "shortfall=restaurants:2,areas:1" in caplog.text


# ---- conservative replacement --------------------------------------------

class Client:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0

    def chat(self, **kwargs):
        self.calls += 1
        return {"message": {"content": self.answers.pop(0)}, "done_reason": "stop"}


def candidate(place_id, name, category, kind, at):
    return {"place_id": place_id, "name": name, "category": category, "region": "부산광역시 수영구",
            "address": "부산광역시 수영구", "is_anchor": False, "activity_kind": kind,
            "latitude": at[0], "longitude": at[1], "opening_hours": None, "event_start_date": None, "event_end_date": None}


SIGHT, FOOD = "NON_FOOD_ACTIVITY", "FOOD_OR_CAFE"
BEACH = candidate(1, "광안리해수욕장", "여행 > 관광,명소 > 해수욕장", SIGHT, (35.153, 129.119))
SQUARE = candidate(2, "만남의광장", "여행 > 관광,명소 > 광장", SIGHT, (35.154, 129.120))
NEAR_PARK = candidate(3, "가까운 공원", "여행 > 공원", SIGHT, (35.160, 129.125))      # ~1.0 km
FAR_TOWER = candidate(4, "먼 전망대", "여행 > 관광,명소 > 전망대", SIGHT, (35.100, 129.032))  # ~10 km
LUNCH = candidate(5, "광안 국밥", "음식점 > 한식", FOOD, (35.155, 129.121))


def entry(sequence, place, start, end, item_type="PLACE"):
    return {"sequence": sequence, "item_type": item_type, "title": place["name"], "place_id": place["place_id"], "start_time": start, "end_time": end}


def repeated_beach_on_day_two():
    return json.dumps({"days": [
        {"visit_date": "2026-10-29", "items": [entry(1, BEACH, "10:00", "11:30"), entry(2, LUNCH, "12:00", "13:00", "MEAL")]},
        {"visit_date": "2026-10-30", "items": [entry(1, SQUARE, "10:00", "11:00"), entry(2, BEACH, "11:30", "12:30")]},
    ]}, ensure_ascii=False)


def generate(client, places, preferences=None):
    provider = ExaonePlanGenerationProvider("http://127.0.0.1:11434", "exaone-test", 60, client)
    trip = {"destination": "부산", "start_date": "2026-10-29", "end_date": "2026-10-30"}
    return provider, provider.generate_plan(trip, preferences or {}, [], ["FOOD"], {}, places)


def test_replacement_is_the_nearest_candidate_not_the_first_listed():
    _, draft = generate(Client(repeated_beach_on_day_two()), [BEACH, SQUARE, FAR_TOWER, NEAR_PARK, LUNCH])
    assert draft.days[1].items[1].place_id == 3


def test_only_a_far_candidate_falls_back_to_the_ai_retry():
    retry = json.dumps({"days": [
        {"visit_date": "2026-10-29", "items": [entry(1, BEACH, "10:00", "11:30")]},
        {"visit_date": "2026-10-30", "items": [entry(1, SQUARE, "10:00", "11:00")]},
    ]}, ensure_ascii=False)
    client = Client(repeated_beach_on_day_two(), retry)
    provider, draft = generate(client, [BEACH, SQUARE, FAR_TOWER, LUNCH])
    assert client.calls == 2
    assert provider.call_diagnostics[0]["validation_reason"].startswith("duplicate_place_id:1;")


def test_low_walking_tolerance_shrinks_the_replacement_radius():
    near_enough = candidate(6, "1.6km 공원", "여행 > 공원", SIGHT, (35.1675, 129.119))  # ~1.6 km from the square
    with pytest.raises(AppError):
        generate(Client(repeated_beach_on_day_two(), repeated_beach_on_day_two()),
                 [BEACH, SQUARE, near_enough, LUNCH], {"walking_tolerance": "VERY_LOW"})
    _, draft = generate(Client(repeated_beach_on_day_two()), [BEACH, SQUARE, near_enough, LUNCH], {"walking_tolerance": "LOW"})
    assert draft.days[1].items[1].place_id == 6
