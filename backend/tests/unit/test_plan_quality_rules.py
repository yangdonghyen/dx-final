"""Server-side checks for a travelable day: meals at meal times, no food-only
days, no repeated spots or areas, realistic stays, no unchecked long legs.

The Jeju (trip 67) and Busan (trip 68) cases mirror the plans saved on the
PC, read-only, so those trips stay regression material without touching them.
"""

from datetime import date, time
from types import SimpleNamespace

import pytest

from app.services.plan_quality_rules import DayStop, PlanQualityRules, parse_window, review_plan, same_location


def place(place_id, name, category, address, latitude, longitude):
    return SimpleNamespace(place_id=place_id, name=name, category=category, address=address, latitude=latitude, longitude=longitude)


ROAD = place(211, "애월해안도로", "여행 > 관광,명소 > 드라이브코스", "제주특별자치도 제주시 애월읍 신엄리 2719-3", 33.4781, 126.3687)
JEJU_FOOD = {
    213: place(213, "애월맛집제주다", "음식점 > 한식", "제주특별자치도 제주시 애월읍 구엄리 1258-3", 33.4820, 126.3754),
    214: place(214, "금돈가", "음식점 > 한식 > 육류,고기", "제주특별자치도 제주시 애월읍 하귀2리 2717", 33.4843, 126.3911),
    217: place(217, "사계바다 통갈치조림", "음식점 > 한식 > 해물,생선", "제주특별자치도 제주시 애월읍 신엄리 2791-5", 33.4784, 126.3573),
    219: place(219, "제주돈아", "음식점 > 한식 > 육류,고기", "제주특별자치도 제주시 애월읍 신엄리 1237-1", 33.4727, 126.3699),
    221: place(221, "어랑어랑생선구이", "음식점 > 한식 > 해물,생선", "제주특별자치도 제주시 애월읍 신엄리 2791-5", 33.4784, 126.3573),
    223: place(223, "망고홀릭", "음식점 > 카페", "제주특별자치도 제주시 애월읍 고내리 459", 33.4705, 126.3416),
    224: place(224, "교촌치킨", "음식점 > 치킨", "제주특별자치도 제주시 애월읍 고내리 1145-1", 33.4665, 126.3373),
    218: place(218, "낭만식당", "음식점 > 한식", "제주특별자치도 제주시 애월읍 고내리 390", 33.4724, 126.3468),
}


def stop(sequence, item_type, start, end, at=None, travel=None):
    return DayStop(sequence, item_type, time.fromisoformat(start), time.fromisoformat(end), at, travel)


def codes(findings, day=None):
    return [finding.code for finding in findings if day is None or finding.day == day]


@pytest.fixture
def rules():
    return PlanQualityRules()


def test_jeju_trip_67_shape_is_flagged_on_every_problem(rules):
    food = JEJU_FOOD
    days = [
        ("1일차", [stop(1, "PLACE", "09:00", "12:00", ROAD), stop(2, "MEAL", "12:30", "13:30", food[213]),
                  stop(3, "FREE_TIME", "13:30", "15:00"), stop(4, "MEAL", "15:00", "17:00", food[214]),
                  stop(5, "FREE_TIME", "17:00", "19:00"), stop(6, "PLACE", "19:00", "20:00", food[223])]),
        ("2일차", [stop(1, "MEAL", "10:00", "12:00", food[217]), stop(2, "FREE_TIME", "12:00", "13:30"),
                  stop(3, "MEAL", "13:30", "15:00", food[219]), stop(4, "FREE_TIME", "15:00", "17:00"),
                  stop(5, "MEAL", "17:00", "19:00", food[221])]),
        ("3일차", [stop(1, "MEAL", "10:00", "11:30", food[224]), stop(2, "FREE_TIME", "11:30", "13:00"),
                  stop(3, "MEAL", "13:00", "14:30", food[218])]),
    ]

    findings = review_plan(days, rules)

    assert set(codes(findings, "1일차")) == {"MEAL_OUTSIDE_WINDOW", "BACK_TO_BACK_MEALS", "MISSING_DINNER"}
    assert {"MEAL_OUTSIDE_WINDOW", "FOOD_ONLY_DAY", "BACK_TO_BACK_MEALS", "DUPLICATE_LOCATION"} <= set(codes(findings, "2일차"))
    assert {"MEAL_OUTSIDE_WINDOW", "FOOD_ONLY_DAY", "BACK_TO_BACK_MEALS"} <= set(codes(findings, "3일차"))
    assert all(finding.severity == "WARNING" for finding in findings)


def test_busan_trip_68_shape_flags_missing_lunch_far_dinner_and_repeated_area(rules):
    beach = place(163, "광안리해수욕장", "여행 > 관광,명소 > 해수욕장,해변", "부산 수영구 광안동 192-20", 35.1532, 129.1190)
    booth = place(173, "플랜비스튜디오", "문화,예술 > 사진 > 사진관,포토스튜디오", "부산 수영구 광안동 192-5", 35.1541, 129.1188)
    street = place(311, "광안리해변테마거리", "여행 > 관광,명소 > 테마거리", "부산 수영구 민락동", 35.1551, 129.1219)
    sinseon = place(146, "신선식당", "음식점 > 한식", "부산 동구 범일동 830-46", 35.1396, 129.0608)
    trail = place(306, "해파랑길 1코스", "여행 > 관광,명소 > 도보여행", "부산 수영구 광안동", 35.1510, 129.1165)
    zoo = place(307, "세븐테마 카페", "여행 > 관광,명소 > 동물원 > 실내동물원", "부산 수영구 민락동 179-11", 35.1547, 129.1199)
    square = place(310, "광안리만남의광장", "여행 > 관광,명소 > 광장", "부산 수영구 민락동 179-19", 35.1540, 129.1197)
    pizza = place(149, "이재모피자 본점", "음식점 > 양식 > 피자", "부산 중구 신창동1가 2-1", 35.1020, 129.0307)
    days = [
        ("1일차", [stop(1, "PLACE", "09:00", "12:00", beach), stop(2, "PLACE", "12:30", "13:30", booth),
                  stop(3, "PLACE", "14:00", "16:00", street), stop(4, "MEAL", "17:30", "19:30", sinseon)]),
        ("2일차", [stop(1, "PLACE", "09:00", "12:00", trail), stop(2, "PLACE", "12:30", "14:00", zoo),
                  stop(3, "PLACE", "14:30", "16:30", square), stop(4, "MEAL", "17:30", "19:30", pizza)]),
    ]

    findings = review_plan(days, rules)

    assert codes(findings, "1일차") == ["MISSING_LUNCH", "UNVERIFIED_LONG_LEG"]
    # 390 sightseeing minutes on day 2 (Phase 3A rule).
    assert codes(findings, "2일차") == ["MISSING_LUNCH", "CROWDED_DAY", "UNVERIFIED_LONG_LEG", "REPEATED_AREA"]
    long_leg = next(finding for finding in findings if finding.code == "UNVERIFIED_LONG_LEG")
    assert long_leg.issue_type == "TRAVEL_TIME_UNKNOWN" and "5.8km" in long_leg.message


def test_a_varied_realistic_day_passes_without_warnings(rules):
    museum = place(1, "국립중앙박물관", "여행 > 관광,명소 > 박물관", "서울 용산구 서빙고로 137", 37.5240, 126.9803)
    lunch = place(2, "용산 국수집", "음식점 > 한식", "서울 용산구 한강대로 1", 37.5290, 126.9680)
    park = place(3, "용산가족공원", "여행 > 공원", "서울 용산구 서빙고로 185", 37.5225, 126.9870)
    cafe = place(4, "한강 카페", "음식점 > 카페", "서울 용산구 이촌로 2", 37.5180, 126.9750)
    dinner = place(5, "이촌 한식당", "음식점 > 한식", "서울 용산구 이촌로 3", 37.5185, 126.9760)
    day = [stop(1, "PLACE", "09:30", "11:30", museum), stop(2, "MEAL", "12:00", "13:00", lunch),
           stop(3, "PLACE", "13:30", "15:30", park), stop(4, "REST", "15:30", "16:00"),
           stop(5, "PLACE", "16:00", "17:00", cafe, travel=12), stop(6, "MEAL", "18:00", "19:00", dinner)]

    assert review_plan([("1일차", day)], rules) == []


def test_meal_rules_follow_the_day_not_a_fixed_clock(rules):
    # Arriving in the afternoon: no lunch is expected, dinner still is.
    afternoon = [stop(1, "PLACE", "15:00", "17:00", ROAD), stop(2, "MEAL", "18:00", "19:00", JEJU_FOOD[213])]
    assert review_plan([("1일차", afternoon)], rules) == []


def test_meal_windows_are_configurable():
    late_lunch = [stop(1, "PLACE", "10:00", "12:00", ROAD), stop(2, "MEAL", "14:15", "15:00", JEJU_FOOD[213])]
    assert "MEAL_OUTSIDE_WINDOW" in codes(review_plan([("1일차", late_lunch)], PlanQualityRules()))
    relaxed = PlanQualityRules.from_windows("07:00-09:30", "11:00-14:30", "17:00-20:00")
    assert "MEAL_OUTSIDE_WINDOW" not in codes(review_plan([("1일차", late_lunch)], relaxed))
    with pytest.raises(ValueError):
        parse_window("14:00-11:00")
    with pytest.raises(ValueError):
        parse_window("noon")


def test_verified_travel_minutes_make_a_long_leg_checkable(rules):
    far = place(9, "먼 식당", "음식점 > 한식", "부산 중구 신창동1가 2-1", 35.1020, 129.0307)
    beach = place(8, "광안리해수욕장", "여행 > 관광,명소", "부산 수영구 광안동 192-20", 35.1532, 129.1190)
    unknown = [stop(1, "PLACE", "15:00", "17:00", beach), stop(2, "MEAL", "18:00", "19:00", far)]
    known = [stop(1, "PLACE", "15:00", "17:00", beach), stop(2, "MEAL", "18:00", "19:00", far, travel=35)]

    assert codes(review_plan([("1일차", unknown)], rules)) == ["UNVERIFIED_LONG_LEG"]
    # A verified route removes the UNKNOWN-leg warning, but it must not hide
    # the actual 35-minute drive immediately before the meal.
    assert codes(review_plan([("1일차", known)], rules)) == ["LONG_MEAL_TRAVEL"]


def test_unrealistic_stays_and_too_many_meals(rules):
    long_visit = [stop(1, "PLACE", "09:00", "14:30", ROAD), stop(2, "MEAL", "15:00", "15:10", JEJU_FOOD[213])]
    assert "LONG_STAY" in codes(review_plan([("1일차", long_visit)], rules))
    short_visit = [stop(1, "PLACE", "17:00", "17:10", ROAD), stop(2, "MEAL", "18:00", "19:00", JEJU_FOOD[213])]
    assert codes(review_plan([("1일차", short_visit)], rules)) == ["SHORT_STAY"]


def test_location_unknown_free_time_does_not_count_as_a_confirmed_rest_break(rules):
    """A flexible gap cannot conceal four continuous sightseeing activities."""
    sights = [
        place(301, "A", "tourist attraction", "Busan 1", 35.15, 129.11),
        place(302, "B", "tourist attraction", "Busan 2", 35.151, 129.111),
        place(303, "C", "tourist attraction", "Busan 3", 35.152, 129.112),
        place(304, "D", "tourist attraction", "Busan 4", 35.153, 129.113),
    ]
    day = [
        stop(1, "PLACE", "09:00", "10:00", sights[0]),
        stop(2, "PLACE", "10:00", "11:00", sights[1]),
        stop(3, "FREE_TIME", "11:00", "12:00"),
        stop(4, "PLACE", "12:00", "13:00", sights[2]),
        stop(5, "PLACE", "13:00", "14:00", sights[3]),
    ]

    assert "CONSECUTIVE_SIGHTS" in codes(review_plan([("1일차", day)], rules))


def test_declared_rest_still_resets_the_sightseeing_run(rules):
    sights = [
        place(311, "A", "tourist attraction", "Busan 1", 35.15, 129.11),
        place(312, "B", "tourist attraction", "Busan 2", 35.151, 129.111),
        place(313, "C", "tourist attraction", "Busan 3", 35.152, 129.112),
        place(314, "D", "tourist attraction", "Busan 4", 35.153, 129.113),
    ]
    day = [
        stop(1, "PLACE", "09:00", "10:00", sights[0]),
        stop(2, "PLACE", "10:00", "11:00", sights[1]),
        stop(3, "REST", "11:00", "12:00"),
        stop(4, "PLACE", "12:00", "13:00", sights[2]),
        stop(5, "PLACE", "13:00", "14:00", sights[3]),
    ]

    assert "CONSECUTIVE_SIGHTS" not in codes(review_plan([("1일차", day)], rules))


def test_same_location_needs_a_full_address():
    assert same_location(JEJU_FOOD[217], JEJU_FOOD[221])
    district = SimpleNamespace(address="부산 수영구 광안동")
    assert not same_location(district, SimpleNamespace(address="부산 수영구 광안동"))
    assert not same_location(SimpleNamespace(address=None), SimpleNamespace(address=None))


def test_validation_stores_quality_problems_as_warning_not_valid(monkeypatch):
    import app.services.plan_validation_service as module
    from tests.unit.test_plan_validation_service import Issues, Items, Places, Session

    for name, replacement in {"PlanItemRepository": Items, "PlaceRepository": Places, "PlanValidationIssueRepository": Issues}.items():
        monkeypatch.setattr(module, name, replacement)
    session = Session()
    session.places = {214: JEJU_FOOD[214], 211: ROAD}
    session.items = [
        SimpleNamespace(item_id=1, visit_date=date(2026, 10, 19), sequence_no=1, place_id=211, item_type="PLACE", start_time=time(9), end_time=time(12), validation_status="UNKNOWN", travel_minutes_from_previous=None),
        SimpleNamespace(item_id=2, visit_date=date(2026, 10, 19), sequence_no=2, place_id=214, item_type="MEAL", start_time=time(15), end_time=time(16), validation_status="UNKNOWN", travel_minutes_from_previous=None),
    ]
    service = module.PlanValidationService(session, rules=PlanQualityRules())

    findings = service.validate(SimpleNamespace(plan_id=1, last_validated_at=None), SimpleNamespace(start_date=date(2026, 10, 19), end_date=date(2026, 10, 19)))

    # Opening-hours uncertainty is recorded by the temporal layer. This test
    # continues to assert the quality-rule finding separately.
    quality_findings = [finding for finding in findings if finding[1] != "OPENING_HOURS_UNKNOWN"]
    assert {message.split(" ")[0] for *_, message in quality_findings} == {"1일차"}
    assert any(code == "OPENING_HOURS_UNKNOWN" for _, code, _, _ in findings)
    assert all(severity == "WARNING" for _, _, severity, _ in findings)
    assert session.items[1].validation_status == "WARNING"
    assert any(issue.issue_type == "OTHER" and issue.item_id == 2 for issue in session.issues)
