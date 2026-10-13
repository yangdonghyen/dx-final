from datetime import date, time
from types import SimpleNamespace

from app.schemas.plan import PlanItemResponse
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.external.routing.provider import RouteEstimate
from app.services.plan_regeneration_preview_service import PlanRegenerationPreviewService
from app.services.plan_travel_time import travel_columns, travel_statuses
from tests.unit.test_plan_edit_service import edit, request  # noqa: F401  (pytest fixture)
from tests.unit.test_plan_generation_service import Place, service  # noqa: F401  (pytest fixture)
from tests.unit.test_plan_regeneration_approval_service import service as approval_service


class Routes:
    """Fake provider keyed by destination place coordinates."""

    def __init__(self, by_destination): self.by_destination = by_destination; self.calls = []

    def route(self, origin_lat, origin_lng, dest_lat, dest_lng, mode):
        self.calls.append((origin_lat, origin_lng, dest_lat, dest_lng, mode))
        return self.by_destination.get((dest_lat, dest_lng))


def stored(place_id, start, minutes=None, sequence=1):
    return SimpleNamespace(place_id=place_id, start_time=start, end_time=time(start.hour, 30) if start else None, sequence_no=sequence, travel_minutes_from_previous=minutes)


def test_seconds_round_up_to_minutes_and_missing_facts_stay_null():
    assert travel_columns(RouteEstimate(60, "CAR"))["travel_minutes_from_previous"] == 1
    assert travel_columns(RouteEstimate(61, "PUBLIC_TRANSIT")) == {
        "transport_mode_from_previous": "PUBLIC_TRANSIT", "travel_minutes_from_previous": 2,
        "travel_distance_meters_from_previous": None,
    }
    for missing in (None, RouteEstimate(0, "CAR"), RouteEstimate(-5, "CAR"), RouteEstimate(300, "MIXED")):
        assert set(travel_columns(missing).values()) == {None}


def test_provider_distance_is_stored_only_when_it_is_a_positive_route_fact():
    assert travel_columns(RouteEstimate(61, "CAR", distance_meters=1234))["travel_distance_meters_from_previous"] == 1234
    assert travel_columns(RouteEstimate(61, "CAR", distance_meters=0))["travel_distance_meters_from_previous"] is None


def test_known_unknown_none_statuses_for_one_day():
    first, rest, known, unknown = stored(1, time(10), sequence=1), stored(None, time(11), sequence=2), stored(2, time(12), 25, 3), stored(3, time(14), None, 4)
    statuses = travel_statuses([first, rest, known, unknown])
    assert [statuses[id(row)] for row in (first, rest, known, unknown)] == ["NONE", "NONE", "KNOWN", "UNKNOWN"]
    single = stored(1, time(10))
    assert travel_statuses([single])[id(single)] == "NONE"


def busan_draft():
    items = [
        PlanDraftItem(1, "PLACE", "해운대", 101, "10:00", "11:30", "r"),
        PlanDraftItem(2, "REST", "휴식", None, "11:30", "12:00", "r"),
        PlanDraftItem(3, "PLACE", "광안리", 104, "12:30", "13:30", "r"),
        PlanDraftItem(4, "PLACE", "감천문화마을", 105, "15:00", "16:00", "r"),
    ]
    return GeneratedPlanDraft(days=[PlanDraftDay(date(2026, 10, 10), items)])


def test_generate_stores_known_leg_and_rest_is_not_added_to_travel(service):
    generator, session, provider, _ = service
    session.places.append(Place(105, "Village", latitude=37.502, longitude=126.902, kakao_place_id="village"))
    provider.draft = busan_draft()
    # 광안리 leg is known (125 s), 감천 leg has no route fact.
    generator.route_provider = Routes({(37.501, 126.901): RouteEstimate(125, "PUBLIC_TRANSIT", distance_meters=1500, walking_seconds=60, transfer_count=0)})

    response = generator.generate(1, 1, [101])

    saved = {item.title: item for item in session.items}
    assert saved["Cafe"].travel_minutes_from_previous == 3  # ceil(125/60); the 30-minute REST is separate
    assert saved["Cafe"].transport_mode_from_previous == "PUBLIC_TRANSIT"
    assert saved["Cafe"].travel_distance_meters_from_previous == 1500
    assert saved["Village"].travel_minutes_from_previous is None and saved["Village"].transport_mode_from_previous is None
    assert saved["Museum"].travel_minutes_from_previous is None
    statuses = [(item.name, item.travel_status, item.travel_minutes_from_previous) for item in response.days[0].items]
    assert statuses == [("Museum", "NONE", None), ("휴식", "NONE", None), ("Cafe", "KNOWN", 3), ("Village", "UNKNOWN", None)]
    assert response.days[0].items[0].place_id == 101  # anchor kept


def test_unavailable_routes_never_store_zero(service):
    generator, session, provider, _ = service
    provider.draft = busan_draft()
    session.places.append(Place(105, "Village", latitude=37.502, longitude=126.902, kakao_place_id="village"))

    response = generator.generate(1, 1, [101])

    assert all(item.travel_minutes_from_previous is None for item in session.items)
    assert [item.travel_status for item in response.days[0].items] == ["NONE", "NONE", "UNKNOWN", "UNKNOWN"]


def test_preview_proposal_carries_travel_and_approve_applies_it_unchanged():
    proposal_item = PlanDraftItem(3, "PLACE", "Museum", 1, "11:00:00", "12:00:00", "moved")
    proposed = PlanRegenerationPreviewService._proposed_item(proposal_item, date(2026, 1, 1), time(11), time(12), RouteEstimate(1201, "CAR"))
    assert (proposed["transport_mode_from_previous"], proposed["travel_minutes_from_previous"]) == ("CAR", 21)

    svc, _, _, preview, rows, _ = approval_service()
    preview.proposed_itinerary["items"][0].update(transport_mode_from_previous="CAR", travel_minutes_from_previous=21)
    # A different live value at approval time must not replace the previewed one.
    svc.generation._validate_route_timing = lambda days, places, trip: {(date(2026, 1, 1), 1): RouteEstimate(3000, "CAR")}

    svc.approve(1, 10, 20)

    museum, rest = rows
    assert (museum.transport_mode_from_previous, museum.travel_minutes_from_previous) == ("CAR", 21)
    assert rest.travel_minutes_from_previous is None


def test_approving_an_older_preview_without_travel_keeps_unknown():
    svc, _, _, _, rows, _ = approval_service()
    svc.approve(1, 10, 20)
    assert all(row.travel_minutes_from_previous is None for row in rows)


def test_manual_reorder_clears_stored_travel_for_that_day(edit):
    service_, s = edit
    s.items[1].transport_mode_from_previous, s.items[1].travel_minutes_from_previous = "CAR", 12

    result = service_.edit(1, 10, request("REORDER", day=1, item_ids=[102, 101]))

    assert all(row.travel_minutes_from_previous is None and row.transport_mode_from_previous is None for row in s.items if row.plan_id == 10)
    # Status follows visit times: 101 (01:00) has no leg before it, 102 (02:00) is now UNKNOWN.
    assert {item.item_id: item.travel_status for item in result.days[0].items} == {101: "NONE", 102: "UNKNOWN"}


def test_add_rest_keeps_place_legs(edit):
    service_, s = edit
    s.items[1].transport_mode_from_previous, s.items[1].travel_minutes_from_previous = "CAR", 12

    service_.edit(1, 10, request("ADD_REST", day=1, after_item_id=101, duration_minutes=30))

    assert s.items[1].travel_minutes_from_previous == 12


def test_item_response_stays_backward_compatible():
    item = PlanItemResponse(item_id=1, place_id=None, name="Rest", start_time=None, end_time=None, validation_status="UNKNOWN")
    body = item.model_dump()
    assert body["travel_status"] is None and body["travel_minutes_from_previous"] is None
    assert {"item_id", "place_id", "name", "start_time", "end_time", "validation_status", "item_type", "latitude"} <= set(body)
