"""Phase 3C: same-slot route optimisation, meals near the day's sights, senior
rest breaks, and area-targeted restaurant candidates.  Coordinates are the
real ones from the Busan 2-day Kakao run; no Ollama, Kakao or database."""

from datetime import date
from types import SimpleNamespace

from app.core.exceptions import AppError
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.external.routing.provider import RouteEstimate
from app.services.external.routing.cached_provider import CachedRouteProvider
from app.services.external.place.provider import PlaceCandidate
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_quality_rules import PlanQualityRules
from app.services.plan_route_optimizer import far_meals, insert_rest_breaks, optimize_routes, route_length
from tests.unit.test_plan_generation_service import NearbyProvider, service  # noqa: F401  (fixture)


def place(place_id, name, category, lat, lng, address="부산 수영구", hours=None, event=None):
    return SimpleNamespace(place_id=place_id, name=name, category=category, latitude=lat, longitude=lng, address=address,
                           verification_status="VERIFIED" if hours else "UNVERIFIED", opening_hours=hours,
                           event_start_date=event, event_end_date=event, kakao_place_id=str(place_id), region="부산")


GWANGALLI = place(163, "광안리해수욕장", "여행 > 관광,명소 > 해수욕장", 35.1532, 129.1190)
HAEUNDAE = place(313, "해운대해수욕장", "여행 > 관광,명소 > 해수욕장", 35.1585, 129.1599)
SONGDO = place(312, "송도해상케이블카", "여행 > 관광,명소 > 케이블카", 35.0766, 129.0234, "부산 서구 암남동")
DADAEPO = place(314, "다대포해수욕장", "여행 > 관광,명소 > 해수욕장", 35.0465, 128.9627, "부산 사하구 다대동")
GAMCHEON = place(317, "감천문화마을", "여행 > 관광,명소", 35.0974, 129.0106, "부산 사하구 감천동")
SINSEON = place(146, "신선식당", "음식점 > 한식", 35.1396, 129.0608, "부산 동구 범일동")
MINRAK = place(326, "민락 국밥", "음식점 > 한식 > 국밥", 35.1567, 129.1343)
PIZZA = place(149, "이재모피자", "음식점 > 양식 > 피자", 35.1020, 129.0307, "부산 중구 신창동")
SHINBALWON = place(328, "신발원", "음식점 > 중식", 35.1150, 129.0390, "부산 동구 초량동")
PLACES = {p.place_id: p for p in (GWANGALLI, HAEUNDAE, SONGDO, DADAEPO, GAMCHEON, SINSEON, MINRAK, PIZZA, SHINBALWON)}

DAY1, DAY2 = date(2026, 10, 29), date(2026, 10, 30)  # Thursday, Friday


def item(sequence, item_type, target, start, end):
    return PlanDraftItem(sequence, item_type, target.name if target else "휴식", target.place_id if target else None, start, end, "model")


def kakao_run_draft():
    """The real Phase 3B itinerary: meals far from the day's sights."""
    return GeneratedPlanDraft([
        PlanDraftDay(DAY1, [item(1, "PLACE", GWANGALLI, "09:00", "12:00"), item(2, "MEAL", SINSEON, "12:30", "13:30"),
                            item(3, "PLACE", HAEUNDAE, "14:00", "16:00"), item(4, "FREE_TIME", None, "16:00", "18:00")]),
        PlanDraftDay(DAY2, [item(1, "PLACE", SONGDO, "09:00", "10:30"), item(2, "MEAL", MINRAK, "11:30", "12:30"),
                            item(3, "PLACE", DADAEPO, "13:00", "15:00"), item(4, "PLACE", GAMCHEON, "15:30", "17:30"),
                            item(5, "MEAL", PIZZA, "18:30", "19:30")]),
    ])


def ids(draft):
    return [[entry.place_id for entry in day.items] for day in draft.days]


def slots(draft):
    return [[(entry.sequence, entry.item_type, entry.start_time, entry.end_time) for entry in day.items] for day in draft.days]


def test_meals_move_next_to_the_days_sights_and_slots_keep_their_times():
    draft = kakao_run_draft()
    before = route_length(draft.days, PLACES)

    optimized, moves = optimize_routes(draft, PLACES, set())

    after = route_length(optimized.days, PLACES)
    assert after[0] < before[0] - 20000 and after[1] < before[1]
    assert optimized.days[0].items[1].place_id == 326  # 민락 lunch beside 광안리, not 동구
    assert slots(optimized) == slots(draft)
    used = [place_id for day in ids(optimized) for place_id in day if place_id]
    assert len(used) == len(set(used))
    assert moves and all(move["gain_m"] >= 500 for move in moves)
    assert ids(draft)[0][1] == 146  # input untouched


def test_anchors_events_and_closed_slots_are_never_used_for_a_move():
    draft = kakao_run_draft()
    optimized, _ = optimize_routes(draft, PLACES, {146, 326})
    assert optimized.days[0].items[1].place_id == 146 and optimized.days[1].items[1].place_id == 326

    closed_at_lunch = place(326, "민락 국밥", "음식점 > 한식 > 국밥", 35.1567, 129.1343, hours={"thursday": {"open": "17:00", "close": "22:00"}})
    optimized, _ = optimize_routes(draft, {**PLACES, 326: closed_at_lunch}, set())
    assert optimized.days[0].items[1].place_id != 326

    festival = place(326, "민락 축제 식당", "음식점 > 한식", 35.1567, 129.1343, event=DAY2)
    optimized, _ = optimize_routes(draft, {**PLACES, 326: festival}, set())
    assert optimized.days[1].items[1].place_id == 326


def test_an_unused_nearby_restaurant_can_take_a_meal_slot():
    draft = GeneratedPlanDraft([PlanDraftDay(DAY2, [item(1, "PLACE", GAMCHEON, "10:00", "12:00"), item(2, "MEAL", MINRAK, "12:30", "13:30"),
                                                    item(3, "PLACE", SONGDO, "14:00", "16:00")])])
    optimized, moves = optimize_routes(draft, PLACES, set())
    assert optimized.days[0].items[1].place_id in {149, 328, 146}
    assert moves[0]["kind"] == "replace"


def test_meal_far_from_every_stop_is_reported_not_replaced_by_force():
    far = {p: PLACES[p] for p in (163, 313, 146)}
    draft = GeneratedPlanDraft([PlanDraftDay(DAY1, [item(1, "PLACE", GWANGALLI, "09:00", "11:00"), item(2, "MEAL", SINSEON, "12:00", "13:00"),
                                                    item(3, "PLACE", HAEUNDAE, "14:00", "16:00")])])
    optimized, moves = optimize_routes(draft, far, set())
    assert moves == []
    assert far_meals(optimized, far) == [{"visit_date": "2026-10-29", "sequence": 2, "place_id": 146, "nearest_stop_m": 5504}]


def test_verified_route_seconds_choose_a_different_order_than_coordinate_proximity():
    """A real route fact, not haversine distance, decides the swap."""
    a = place(901, "A", "travel", 35.1500, 129.1000)
    b = place(902, "B", "travel", 35.1501, 129.1001)
    c = place(903, "C", "travel", 35.1800, 129.1600)
    candidates = {row.place_id: row for row in (a, b, c)}
    draft = GeneratedPlanDraft([PlanDraftDay(DAY1, [
        item(1, "PLACE", a, "09:00", "10:00"),
        item(2, "PLACE", b, "10:30", "11:30"),
        item(3, "PLACE", c, "12:00", "13:00"),
    ])])
    seconds = {
        (901, 902): 3600, (902, 903): 3600,
        (901, 903): 120, (903, 902): 120,
        (902, 901): 3600, (903, 901): 3600,
    }

    optimized, moves = optimize_routes(
        draft, candidates, set(),
        route_metric=lambda first, second: seconds.get((first.place_id, second.place_id)),
        minimum_gain=60,
        gain_key="gain_seconds",
    )

    assert [entry.place_id for entry in optimized.days[0].items] == [901, 903, 902]
    assert moves and moves[0]["gain_seconds"] >= 60


def test_unknown_route_metric_never_falls_back_to_a_made_up_duration_or_swap():
    draft = kakao_run_draft()
    optimized, moves = optimize_routes(draft, PLACES, set(), route_metric=lambda *_: None, minimum_gain=60)
    assert ids(optimized) == ids(draft)
    assert moves == []


def test_generation_uses_mocked_car_route_seconds_for_route_optimization():
    a = place(911, "A", "travel", 35.1500, 129.1000)
    b = place(912, "B", "travel", 35.1501, 129.1001)
    c = place(913, "C", "travel", 35.1800, 129.1600)
    candidates = {row.place_id: row for row in (a, b, c)}
    draft = GeneratedPlanDraft([PlanDraftDay(DAY1, [
        item(1, "PLACE", a, "09:00", "10:00"),
        item(2, "PLACE", b, "10:30", "11:30"),
        item(3, "PLACE", c, "12:00", "13:00"),
    ])])
    by_coordinate = {round(row.latitude, 4): row.place_id for row in candidates.values()}
    seconds = {(911, 912): 3600, (912, 913): 3600, (911, 913): 120, (913, 912): 120}

    class Routes:
        def route(self, _origin_lat, _origin_lng, destination_lat, _destination_lng, mode):
            origin_id = by_coordinate[round(_origin_lat, 4)]
            destination_id = by_coordinate[round(destination_lat, 4)]
            duration = seconds.get((origin_id, destination_id))
            return RouteEstimate(duration, "CAR", distance_meters=100) if mode == "CAR" and duration else None

    generation = gen()
    generation.route_provider = Routes()
    trip = SimpleNamespace(trip_id=99, start_date=DAY1, end_date=DAY1, transport_mode="CAR")
    chosen = generation._optimize_routes(draft, candidates, set(), trip, {})

    assert generation.last_route_optimization["applied"] is True, generation.last_route_optimization
    assert [entry.place_id for entry in chosen.days[0].items] == [911, 913, 912]
    assert generation.last_route_optimization["metric"] == "ROUTE_SECONDS"
    assert generation.last_route_optimization["route_seconds_after"] < generation.last_route_optimization["route_seconds_before"]


def test_real_route_optimization_stays_inside_the_existing_candidate_and_total_budgets():
    a = place(921, "A", "travel", 35.1500, 129.1000)
    b = place(922, "B", "travel", 35.1501, 129.1001)
    c = place(923, "C", "travel", 35.1510, 129.1010)
    candidates = {row.place_id: row for row in (a, b, c)}
    draft = GeneratedPlanDraft([PlanDraftDay(DAY1, [
        item(1, "PLACE", a, "09:00", "10:00"), item(2, "PLACE", b, "10:30", "11:30"), item(3, "PLACE", c, "12:00", "13:00"),
    ])])

    class CountingRoutes:
        def __init__(self): self.calls = 0
        def route(self, *_args):
            self.calls += 1
            return RouteEstimate(120, "CAR", distance_meters=100)

    inner = CountingRoutes()
    generation = gen()
    generation.route_provider = CachedRouteProvider(inner, max_calls=3, max_candidate_calls=2)
    trip = SimpleNamespace(trip_id=100, start_date=DAY1, end_date=DAY1, transport_mode="CAR")
    generation._optimize_routes(draft, candidates, set(), trip, {})

    assert generation.route_provider.calls <= 3
    assert generation.route_provider.candidate_calls <= 2
    assert inner.calls == generation.route_provider.calls


def test_rest_breaks_follow_stated_preferences_only():
    draft = kakao_run_draft()
    rested, breaks = insert_rest_breaks(draft, PLACES, set(), {"travel_style": "SLOW"})
    day_two = rested.days[1].items
    assert [entry.item_type for entry in day_two][:4] == ["PLACE", "MEAL", "PLACE", "REST"]  # between 다대포 and 감천
    assert (day_two[2].end_time, day_two[3].start_time, day_two[3].end_time) == ("14:30", "14:30", "15:00")
    assert [entry.sequence for entry in day_two] == list(range(1, len(day_two) + 1))
    assert len(breaks) == 2

    assert insert_rest_breaks(draft, PLACES, set(), {"rest_frequency": "LOW", "travel_style": "SLOW"})[1] == []
    assert insert_rest_breaks(draft, PLACES, {163, 313, 312, 314, 317}, {"travel_style": "SLOW"})[1] == []  # anchors
    assert len(insert_rest_breaks(draft, PLACES, set(), {"travel_style": "STANDARD"})[1]) == 1  # only 광안리 (180 min)


def gen():
    generation = PlanGenerationService(None, None)
    generation._quality_rules = PlanQualityRules()
    return generation


def test_service_keeps_the_model_draft_when_the_optimised_one_fails_validation():
    generation = gen()
    trip = SimpleNamespace(trip_id=68, start_date=DAY1, end_date=DAY2)
    chosen = generation._optimize_routes(kakao_run_draft(), PLACES, set(), trip, {"travel_style": "SLOW"})
    assert generation.last_route_optimization["applied"] is True
    assert chosen.days[0].items[2].place_id == 326 or chosen.days[0].items[1].place_id == 326

    def refuse(*_):
        raise AppError("OUTSIDE_OPENING_HOURS", "no", 422)

    generation._validate_temporal_draft = refuse
    original = kakao_run_draft()
    assert ids(generation._optimize_routes(original, PLACES, set(), trip, {})) == ids(original)
    assert generation.last_route_optimization["reverted"] == "validation:OUTSIDE_OPENING_HOURS"


def test_restaurants_are_ordered_by_the_sight_areas_they_serve():
    ordered = PlanGenerationService._restaurants_by_area([SINSEON, MINRAK, PIZZA], [DADAEPO, GWANGALLI, GAMCHEON])
    assert [row.place_id for row in ordered] == [326, 149, 146]


class AreaSearch(NearbyProvider):
    def __init__(self):
        super().__init__()
        self.searches = []

    def search(self, query, region):
        self.searches.append(query)
        if query == "사하구 맛집":
            return [PlaceCandidate("KAKAO", "far-1", "해운대 갈비", "FD6 음식점 > 한식", "부산 해운대구 중동", 35.163, 129.163, None, None),
                    PlaceCandidate("KAKAO", "near-1", "다대포 횟집", "FD6 음식점 > 한식 > 회", "부산 사하구 다대동", 35.048, 128.965, None, None)]
        return []


def test_a_sight_area_without_a_nearby_restaurant_gets_a_district_search(service):
    generator, session, _, _ = service
    trip = session.trips[1]
    trip.destination = "부산"
    from tests.unit.test_plan_generation_service import Place
    session.places = [Place(500, "다대포해수욕장", "여행 > 관광,명소", "부산", "부산 사하구 다대동", 35.0465, 128.9627, "s-500"),
                      Place(501, "광안리 식당", "음식점 > 한식", "부산", "부산 수영구 광안동", 35.1530, 129.1185, "f-501")]
    generator.place_provider = AreaSearch()

    found = generator._meal_backfill(trip, list(session.places), needed=1)

    assert "사하구 맛집" in generator.place_provider.searches
    assert [place.name for place in found] == ["다대포 횟집"]  # the far result is not taken
