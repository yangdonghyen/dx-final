"""Offline wiring tests for the isolated initial-plan evaluator."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_initial_plan_generation.py"
spec = importlib.util.spec_from_file_location("initial_plan_eval", SCRIPT)
evaluation = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(evaluation)


def test_unavailable_route_mode_never_produces_a_route_fact():
    provider, metadata = evaluation.route_provider_for("unavailable")

    assert provider.route(37.5, 127.0, 37.6, 127.1, "CAR") is None
    assert metadata["calls"] == []


def test_mock_route_mode_is_cached_and_keeps_unsupported_mode_unknown():
    provider, metadata = evaluation.route_provider_for("mock")

    first = provider.route(37.5, 127.0, 37.6, 127.1, "CAR")
    second = provider.route(37.5, 127.0, 37.6, 127.1, "CAR")

    assert first == second
    assert (first.mode, first.duration_seconds, first.distance_meters) == ("CAR", 600, 1600)
    assert len(metadata["calls"]) == 1
    assert provider.route(37.5, 127.0, 37.6, 127.1, "MIXED") is None
    assert metadata["calls"][-1]["status"] == "UNKNOWN"


def test_route_report_metrics_do_not_treat_straight_distance_as_api_fact():
    generated = {
        "places": [
            {"place_id": 1, "name": "A", "latitude": 37.5, "longitude": 127.0},
            {"place_id": 2, "name": "B", "latitude": 37.6, "longitude": 127.1},
        ],
        "plan_items": [
            {"visit_date": "2026-01-01", "place_id": 1, "start_time": "10:00:00", "end_time": "11:00:00"},
            {"visit_date": "2026-01-01", "place_id": 2, "start_time": "11:30:00", "end_time": "12:00:00",
             "travel_minutes_from_previous": 10, "travel_distance_meters_from_previous": 1600},
        ],
    }
    metrics = evaluation.route_metrics(
        {"mode": "mock", "source": "fixture", "calls": [{"elapsed_ms": 1, "status": "KNOWN"}]}, generated
    )
    leg = evaluation.route_risk(generated)[0]

    assert metrics["stored_known_legs"] == 1
    assert leg["verified_distance_meters"] == 1600
    assert leg["straight_km"] != 1.6


def test_scores_count_only_located_legs_not_the_first_stop_of_each_day():
    data = {
        "places": [
            {"place_id": 1, "name": "A", "category": "AT4", "address": "A 1", "kakao_place_id": "a", "latitude": 37.5, "longitude": 127.0},
            {"place_id": 2, "name": "B", "category": "FD6", "address": "A 2", "kakao_place_id": "b", "latitude": 37.51, "longitude": 127.01},
            {"place_id": 3, "name": "C", "category": "AT4", "address": "A 3", "kakao_place_id": "c", "latitude": 37.6, "longitude": 127.1},
            {"place_id": 4, "name": "D", "category": "FD6", "address": "A 4", "kakao_place_id": "d", "latitude": 37.61, "longitude": 127.11},
        ],
        "plan_items": [
            {"visit_date": "2026-10-26", "place_id": 1, "item_type": "PLACE", "start_time": "09:00:00", "end_time": "11:00:00"},
            {"visit_date": "2026-10-26", "place_id": 2, "item_type": "MEAL", "start_time": "12:00:00", "end_time": "13:00:00", "travel_minutes_from_previous": 10, "travel_distance_meters_from_previous": 1600},
            {"visit_date": "2026-10-27", "place_id": 3, "item_type": "PLACE", "start_time": "09:00:00", "end_time": "11:00:00"},
            {"visit_date": "2026-10-27", "place_id": 4, "item_type": "MEAL", "start_time": "12:00:00", "end_time": "13:00:00", "travel_minutes_from_previous": 10, "travel_distance_meters_from_previous": 1600},
        ],
    }

    score = evaluation.auto_score(data, [], [], "SLOW")

    assert len(evaluation.route_risk(data)) == 2
    assert not any("UNKNOWN" in item for item in score["unverified"])


def test_undecided_rest_gets_partial_rest_credit_only():
    stops = [
        ({"visit_date": "2026-10-26", "item_type": "REST", "title": evaluation.REST_CAFE_UNDECIDED}, None),
        ({"visit_date": "2026-10-27", "item_type": "REST", "title": "Confirmed rest"}, None),
    ]

    assert evaluation.rest_coverage_credits(stops, ["2026-10-26", "2026-10-27"]) == 1.5
