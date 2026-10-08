from datetime import date, datetime, timedelta, time
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.services.plan_regeneration_approval_service import PlanRegenerationApprovalService


class Session:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def item(item_id, place_id, sequence, item_type, start, end, title):
    return SimpleNamespace(item_id=item_id, plan_id=10, place_id=place_id, sequence_no=sequence, item_type=item_type, visit_date=date(2026, 1, 1), start_time=start, end_time=end, title=title, validation_status="VALID")


def service():
    svc = PlanRegenerationApprovalService.__new__(PlanRegenerationApprovalService)
    svc.session = Session()
    plan = SimpleNamespace(plan_id=10, trip_id=1, current_version=4)
    trip = SimpleNamespace(trip_id=1, user_id=1, start_date=date(2026, 1, 1), end_date=date(2026, 1, 1))
    rows = [item(100, 1, 1, "PLACE", time(10), time(11), "Museum"), item(101, None, 2, "REST", time(12), time(12, 30), "Rest")]
    snapshot = {"items": [svc._snapshot(row) for row in rows]}
    preview = SimpleNamespace(preview_id=20, plan_id=10, user_id=1, status="PENDING", base_version=4, expires_at=datetime.utcnow() + timedelta(minutes=30), current_itinerary_snapshot=snapshot, proposed_itinerary={"items": [
        {"place_id": 1, "visit_date": "2026-01-01", "sequence_no": 1, "item_type": "PLACE", "title": "Museum", "start_time": "11:00:00", "end_time": "12:00:00", "recommendation_reason": "moved"},
        {"place_id": None, "visit_date": "2026-01-01", "sequence_no": 2, "item_type": "REST", "title": "Rest", "start_time": "13:00:00", "end_time": "13:30:00", "recommendation_reason": "rest"},
    ]}, reason="USER_FATIGUE", applied_at=None)
    revisions = []
    candidates = {1: SimpleNamespace(place_id=1, name="Museum")}
    svc.plans = SimpleNamespace(get_for_update=lambda value: plan if value == 10 else None)
    svc.trips = SimpleNamespace(get=lambda value: trip if value == 1 else None)
    svc.previews = SimpleNamespace(get_for_update=lambda value: preview if value == 20 else None, is_expired=lambda value, now: value.expires_at <= now, set_status=lambda value, status, **fields: (setattr(value, "status", status), [setattr(value, key, field) for key, field in fields.items()]))
    svc.items = SimpleNamespace(list=lambda value: list(rows), delete=lambda value: rows.remove(value), create=lambda plan_id, **fields: rows.append(SimpleNamespace(item_id=200 + len(rows), plan_id=plan_id, **fields)))
    svc.revisions = SimpleNamespace(create=lambda plan_id, **fields: revisions.append(fields))
    svc.generation = SimpleNamespace(
        _input=lambda value: ({}, {}, [], [], {}, [], {1}, candidates),
        _date_skeleton=lambda value: [date(2026, 1, 1)],
        _canonical_item_type=lambda value: "PLACE",
        _validate_draft=lambda draft, ids: [(date(2026, 1, 1), [(entry, time.fromisoformat(entry.start_time), time.fromisoformat(entry.end_time)) for entry in draft.days[0].items])],
        _validate_temporal_draft=lambda days, places: None,
        _validate_route_timing=lambda days, places, trip: None,
        _validate_activity_diversity=lambda days, places, trip: None,
        _provider_error=lambda: AppError("AI_SCHEMA_VALIDATION_FAILED", "invalid", 502),
    )
    return svc, plan, trip, preview, rows, revisions


def test_approve_replaces_items_creates_revision_increments_version_and_applies_preview():
    svc, plan, _, preview, rows, revisions = service()
    response = svc.approve(1, 10, 20)
    assert response.status == "APPLIED" and response.current_version == 5 and response.approved is True
    assert plan.current_version == 5 and preview.status == "APPLIED" and preview.applied_at is not None
    assert len(revisions) == 1 and revisions[0]["revision_no"] == 4 and revisions[0]["snapshot"]["items"][0]["item_id"] == 100
    assert [(row.title, row.start_time, row.validation_status) for row in rows] == [("Museum", time(11), "UNKNOWN"), ("Rest", time(13), "UNKNOWN")]
    assert svc.session.commits == 1


def test_cancel_only_changes_pending_preview():
    svc, plan, _, preview, rows, revisions = service()
    response = svc.cancel(1, 10, 20)
    assert response.status == "CANCELLED" and response.current_version is None
    assert preview.status == "CANCELLED" and plan.current_version == 4 and len(rows) == 2 and revisions == []


@pytest.mark.parametrize("mutate,code", [
    (lambda svc, plan, trip, preview, rows: setattr(preview, "status", "APPLIED"), "PREVIEW_NOT_PENDING"),
    (lambda svc, plan, trip, preview, rows: setattr(preview, "expires_at", datetime.utcnow() - timedelta(seconds=1)), "PREVIEW_EXPIRED"),
    (lambda svc, plan, trip, preview, rows: setattr(plan, "current_version", 5), "PREVIEW_VERSION_CONFLICT"),
    (lambda svc, plan, trip, preview, rows: preview.proposed_itinerary["items"][0].update(place_id=999), "AI_SCHEMA_VALIDATION_FAILED"),
    (lambda svc, plan, trip, preview, rows: preview.proposed_itinerary["items"][1].update(start_time="11:30:00", end_time="12:30:00"), "TIME_CONFLICT"),
])
def test_approve_conflicts_preserve_current_items(mutate, code):
    svc, plan, trip, preview, rows, revisions = service(); before = list(rows)
    mutate(svc, plan, trip, preview, rows)
    with pytest.raises(AppError) as error: svc.approve(1, 10, 20)
    assert error.value.code == code and rows == before and revisions == [] and svc.session.rollbacks == 1


def test_approve_blocks_other_user_other_plan_and_save_failure_rolls_back():
    svc, plan, trip, preview, rows, revisions = service()
    trip.user_id = 2
    with pytest.raises(AppError) as error: svc.approve(1, 10, 20)
    assert error.value.code == "FORBIDDEN" and len(rows) == 2
    svc, plan, trip, preview, rows, revisions = service(); preview.plan_id = 11
    with pytest.raises(AppError) as error: svc.approve(1, 10, 20)
    assert error.value.code == "PREVIEW_NOT_FOUND" and len(rows) == 2
    svc, plan, trip, preview, rows, revisions = service(); svc.revisions.create = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("write failed"))
    with pytest.raises(RuntimeError): svc.approve(1, 10, 20)
    assert svc.session.rollbacks == 1 and plan.current_version == 4 and len(rows) == 2 and preview.status == "PENDING"
