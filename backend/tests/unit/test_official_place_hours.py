from datetime import date, datetime
from types import SimpleNamespace

from app.services.official_place_hours import (
    OfficialPlaceHoursEvidence,
    apply_official_hours_evidence,
)
from app.services.place_temporal_validation import opening_hours_match


def _evidence():
    weekly_summer = {day: {"open": "09:00", "close": "18:00"} for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
    weekly_winter = {day: {"open": "09:00", "close": "17:00"} for day in weekly_summer}
    return OfficialPlaceHoursEvidence(
        source_url="https://official.example.test/place", source_name="Official tourism guide",
        checked_at=datetime(2026, 10, 13, 9), applies_to="VILLAGE_VISITOR_GUIDANCE",
        official_name="Gamcheon Culture Village", official_address="Busan Saha-gu Gamcheon-dong 1-17",
        latitude=35.0974087, longitude=129.0105608, facility_type="TOURIST_ATTRACTION",
        seasonal=[{"months": list(range(3, 11)), "weekly": weekly_summer}, {"months": [11, 12, 1, 2], "weekly": weekly_winter}],
        closed_days="Open all year",
    )


def _place():
    return SimpleNamespace(name="Gamcheon Culture Village", address="Busan Saha-gu Gamcheon-dong 1-17", latitude=35.0974087, longitude=129.0105608, category="AT4 > tourist attraction", opening_hours=None, closed_days=None, verification_status="UNKNOWN", details_updated_at=None)


def test_verified_official_seasonal_hours_reject_october_closing_conflict():
    place = _place()
    assert apply_official_hours_evidence(place, _evidence()) is True
    assert place.opening_hours["source"] == "OFFICIAL_PLACE_SOURCE"
    assert place.opening_hours["applies_to"] == "VILLAGE_VISITOR_GUIDANCE"
    from datetime import time
    assert opening_hours_match(place, date(2026, 10, 26), time(16, 32), time(18, 2)) is False


def test_verified_official_winter_hours_use_november_closing_time():
    place = _place()
    apply_official_hours_evidence(place, _evidence())
    from datetime import time
    assert opening_hours_match(place, date(2026, 11, 2), time(16), time(17, 1)) is False


def test_official_evidence_never_matches_name_or_coordinates_alone():
    place = _place()
    wrong_address = _evidence().__class__(**{**_evidence().__dict__, "official_address": "Busan Haeundae-gu Other-dong 1-17"})
    assert apply_official_hours_evidence(place, wrong_address) is False
    assert place.verification_status == "UNKNOWN"
