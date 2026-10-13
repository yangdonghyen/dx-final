"""Offline itinerary-quality profiles; no provider, database, or network use."""

from datetime import time
from types import SimpleNamespace

from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_quality_rules import DayStop, PlanQualityRules, review_plan
from app.services.plan_route_optimizer import rest_policy


def _place(place_id, category, latitude, longitude):
    return SimpleNamespace(
        place_id=place_id,
        name=f"place-{place_id}",
        category=category,
        address=f"fixture address {place_id}",
        latitude=latitude,
        longitude=longitude,
    )


def _stop(sequence, item_type, start, end, place=None, travel=None):
    return DayStop(
        sequence, item_type, time.fromisoformat(start), time.fromisoformat(end), place, travel,
    )


def test_busan_two_day_slow_profile_needs_declared_rest_not_generic_free_time():
    beach = _place(1, "tourist attraction", 35.153, 129.119)
    village = _place(2, "cultural attraction", 35.098, 129.010)
    lunch = _place(3, "FD6 restaurant", 35.150, 129.110)
    day = [
        _stop(1, "PLACE", "09:00", "10:30", beach),
        _stop(2, "REST", "10:30", "11:00"),
        _stop(3, "MEAL", "12:00", "13:00", lunch, travel=20),
        _stop(4, "PLACE", "14:00", "15:30", village, travel=31),
    ]

    assert rest_policy({"travel_style": "SLOW"}) == (90, 1)
    assert review_plan([("day-1", day)], PlanQualityRules()) == []


def test_daejeon_low_walking_profile_uses_known_rest_policy_without_inventing_accessibility():
    museum = _place(10, "cultural facility", 36.350, 127.385)
    restaurant = _place(11, "FD6 restaurant", 36.351, 127.386)
    day = [
        _stop(1, "PLACE", "10:00", "11:30", museum),
        _stop(2, "REST", "11:30", "12:00"),
        _stop(3, "MEAL", "12:00", "13:00", restaurant, travel=8),
    ]

    assert rest_policy({"walking_tolerance": "LOW"}) == (90, 1)
    # The quality rules use only the supplied category/timing/route fact; they
    # deliberately make no indoor or accessibility assertion for the museum.
    assert review_plan([("day-1", day)], PlanQualityRules()) == []


def test_standard_profile_can_offer_three_sights_without_slow_style_density_rule():
    sights = [_place(20 + number, "tourist attraction", 35.16 + number / 1000, 129.12) for number in range(3)]
    lunch = _place(30, "FD6 restaurant", 35.1605, 129.1205)
    day = [
        _stop(1, "PLACE", "09:00", "10:00", sights[0]),
        _stop(2, "PLACE", "10:15", "11:15", sights[1], travel=5),
        _stop(3, "MEAL", "12:00", "13:00", lunch, travel=7),
        _stop(4, "PLACE", "14:00", "15:00", sights[2], travel=9),
    ]

    assert PlanGenerationService._candidate_targets(1, {"travel_style": "STANDARD"})["sights"] == 3
    assert "CONSECUTIVE_SIGHTS" not in [finding.code for finding in review_plan([("day-1", day)], PlanQualityRules())]
