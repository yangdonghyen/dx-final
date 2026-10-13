from datetime import date, datetime, time
from types import SimpleNamespace

from app.core.exceptions import AppError
from app.services.place_hours_enrichment_service import (
    PlaceHoursEnrichmentService,
    tour_hours_snapshot,
)
from app.services.place_temporal_validation import opening_hours_match


class Session:
    def __init__(self):
        self.flushes = 0

    def flush(self):
        self.flushes += 1


class Provider:
    def __init__(self, detail=None, error=None):
        self.detail = detail or {}
        self.error = error
        self.calls = []

    def get_place_detail(self, content_id, **kwargs):
        self.calls.append(content_id)
        if self.error:
            raise self.error
        return self.detail


def _place(content_id="100"):
    return SimpleNamespace(
        place_id=1, tour_content_id=content_id, opening_hours=None,
        closed_days=None, verification_status="UNKNOWN", details_updated_at=None,
    )


def test_explicit_daily_tour_hours_are_verified_and_allow_a_visit():
    session, place = Session(), _place()
    provider = Provider({"operating_hours": "\ub9e4\uc77c 09:00~18:00", "rest_date": None})
    service = PlaceHoursEnrichmentService(session, provider, now=lambda: datetime(2026, 10, 12, 9, 0))

    stats = service.enrich([place])

    assert stats == {"linked": 1, "verified": 1, "partial": 0, "provider_error": 0, "budget_skipped": 0}
    assert place.verification_status == "VERIFIED"
    assert place.opening_hours["source"] == "TOUR_API"
    assert place.opening_hours["checked_at"] == "2026-10-12T09:00:00+00:00"
    assert opening_hours_match(place, date(2026, 10, 12), time(10), time(11)) is True


def test_tour_hours_reject_a_visit_after_closing_without_inventing_a_shift():
    snapshot, status, _ = tour_hours_snapshot(
        {"operating_hours": "\ub9e4\uc77c 09:00~18:00", "rest_date": None}, datetime(2026, 10, 12, 9, 0)
    )
    place = SimpleNamespace(opening_hours=snapshot, verification_status=status)

    assert opening_hours_match(place, date(2026, 10, 12), time(17), time(19)) is False


def test_regular_closure_is_a_confirmed_conflict():
    snapshot, status, closed_days = tour_hours_snapshot(
        {"operating_hours": "\ub9e4\uc77c 09:00~18:00", "rest_date": "\ub9e4\uc8fc \uc6d4\uc694\uc77c \ud734\ubb34"}, datetime(2026, 10, 12, 9, 0)
    )
    place = SimpleNamespace(opening_hours=snapshot, verification_status=status, closed_days=closed_days)

    assert opening_hours_match(place, date(2026, 10, 12), time(10), time(11)) is False  # Monday
    assert opening_hours_match(place, date(2026, 10, 13), time(10), time(11)) is True


def test_unparseable_official_text_stays_partial_and_unknown():
    snapshot, status, _ = tour_hours_snapshot(
        {"operating_hours": "\uc0c1\uc138 \ubb38\uc758", "rest_date": "\uc5c5\uc7a5 \uc0ac\uc815\uc5d0 \ub530\ub984"}, datetime(2026, 10, 12, 9, 0)
    )
    place = SimpleNamespace(opening_hours=snapshot, verification_status=status)

    assert status == "PARTIAL"
    assert opening_hours_match(place, date(2026, 10, 12), time(10), time(11)) is None


def test_provider_failure_does_not_change_existing_unknown_hours():
    session, place = Session(), _place()
    provider = Provider(error=AppError("TOUR_API_TIMEOUT", "timeout", 504))

    stats = PlaceHoursEnrichmentService(session, provider).enrich([place])

    assert stats == {"linked": 1, "verified": 0, "partial": 0, "provider_error": 1, "budget_skipped": 0}
    assert place.verification_status == "UNKNOWN"
    assert place.opening_hours is None
    assert session.flushes == 1


def test_unlinked_kakao_place_makes_no_tour_api_call():
    session, place, provider = Session(), _place(content_id=None), Provider()

    assert PlaceHoursEnrichmentService(session, provider).enrich([place])["linked"] == 0
    assert provider.calls == []
    assert session.flushes == 0


def test_enrichment_caps_linked_places_without_expanding_external_calls():
    session, provider = Session(), Provider({"operating_hours": "\ub9e4\uc77c 09:00~18:00", "rest_date": None})
    stats = PlaceHoursEnrichmentService(session, provider, max_places=1).enrich([_place("1"), _place("2")])

    assert stats["linked"] == 1 and stats["budget_skipped"] == 1
    assert provider.calls == ["1"]
