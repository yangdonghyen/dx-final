from datetime import date, time
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.schemas.plan import PlanRegenerateRequest
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.plan_revision_service import PlanRevisionService


class Session:
    def __init__(self): self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def item(item_id, sequence=1):
    return SimpleNamespace(item_id=item_id, plan_id=10, place_id=1, visit_date=date(2026, 1, 1), sequence_no=sequence, item_type="PLACE", title="Museum", start_time=time(10), end_time=time(11), validation_status="VALID")


def service():
    svc = PlanRevisionService.__new__(PlanRevisionService)
    svc.session = Session()
    plan = SimpleNamespace(plan_id=10, trip_id=1, status="DRAFT", current_version=1, confirmed_at=None)
    trip = SimpleNamespace(trip_id=1, user_id=1, status="DRAFT", start_date=date(2026, 1, 1))
    rows = [item(100)]
    svc.plans = SimpleNamespace(get=lambda plan_id: plan if plan_id == 10 else None)
    svc.trips = SimpleNamespace(get=lambda trip_id: trip if trip_id == 1 else None)
    svc.items = SimpleNamespace(list=lambda plan_id: list(rows), delete=lambda row: rows.remove(row), create=lambda plan_id, **fields: rows.append(SimpleNamespace(item_id=200 + len(rows), plan_id=plan_id, **fields)))
    revisions = []
    svc.revisions = SimpleNamespace(create=lambda plan_id, **fields: revisions.append(fields))
    issues = []
    svc.issues = SimpleNamespace(list_open=lambda plan_id: list(issues))
    svc.validation = SimpleNamespace(validate=lambda plan, trip: [])
    draft = GeneratedPlanDraft([PlanDraftDay(date(2026, 1, 1), [PlanDraftItem(1, "PLACE", "New museum", 1, "10:00", "11:00", "mock")])])
    svc.provider = SimpleNamespace(regenerate_plan=lambda *args: draft)
    svc.generation = SimpleNamespace(_input=lambda trip: ({}, {}, [], [], {"raw_interest_codes": []}, [], {1}, {1: SimpleNamespace(place_id=1, name="Museum", category="CULTURE")}), _prepare_draft=lambda draft, places, anchors: draft, _validate_draft=lambda draft, ids: [(date(2026, 1, 1), [(draft.days[0].items[0], time(10), time(11))])], _validate_temporal_draft=lambda days, places: None, _provider_error=lambda: AppError("AI_SCHEMA_VALIDATION_FAILED", "invalid", 502))
    return svc, plan, trip, rows, revisions, issues


def test_regenerate_snapshots_replaces_items_validates_and_increments_version():
    svc, plan, _, rows, revisions, _ = service()
    response = svc.regenerate(1, 10, PlanRegenerateRequest(reason="USER_FATIGUE", instruction="Less walking"))
    assert revisions[0]["revision_type"] == "USER_FATIGUE"
    assert revisions[0]["snapshot"]["items"][0]["item_id"] == 100
    assert plan.current_version == 2 and rows[0].title == "New museum"
    assert response.current_version == 2 and svc.session.commits == 1


def test_regenerate_forwards_the_normalized_interests_from_shared_generation_input():
    svc, _, _, _, _, _ = service()
    received_interests = []
    received_contexts = []
    svc.generation._input = lambda trip: ({}, {}, [], ["CAFE", "FOOD", "NATURE"], {"raw_interest_codes": ["SEA", "CITY", "REST"]}, [], {1}, {1: SimpleNamespace(place_id=1)})
    original_provider = svc.provider
    svc.provider = SimpleNamespace(
        regenerate_plan=lambda *args: received_interests.append(args[3]) or received_contexts.append(args[4]) or original_provider.regenerate_plan(*args)
    )

    svc.regenerate(1, 10, PlanRegenerateRequest(reason="USER_FATIGUE", instruction="Less walking"))

    assert received_interests == [["CAFE", "FOOD", "NATURE"]]
    assert received_contexts == [{"raw_interest_codes": ["SEA", "CITY", "REST"]}]


def test_regenerate_forwards_current_itinerary_and_flutter_feedback_codes():
    svc, _, _, _, _, _ = service()
    received = []
    original_provider = svc.provider
    svc.provider = SimpleNamespace(
        regenerate_plan=lambda *args: received.append(args) or original_provider.regenerate_plan(*args)
    )

    svc.regenerate(
        1,
        10,
        PlanRegenerateRequest(
            reason="USER_FATIGUE",
            instruction="Make the route easier",
            feedback_codes=["walking", "places", "travel", "rest"],
        ),
    )

    assert received[0][8] == [{"item_id": 100, "place_id": 1, "visit_date": "2026-01-01", "sequence_no": 1, "item_type": "PLACE", "title": "Museum", "start_time": "10:00:00", "end_time": "11:00:00", "validation_status": "VALID"}]
    assert received[0][9] == ["walking", "places", "travel", "rest"]


def test_regenerate_rejects_other_user_and_rolls_back_mid_transaction():
    svc, _, _, rows, _, _ = service()
    with pytest.raises(AppError, match="own this trip"): svc.regenerate(2, 10, PlanRegenerateRequest(reason="WEATHER_CHANGE", instruction="Indoors"))
    svc.validation.validate = lambda plan, trip: (_ for _ in ()).throw(RuntimeError("validation failure"))
    with pytest.raises(RuntimeError): svc.regenerate(1, 10, PlanRegenerateRequest(reason="WEATHER_CHANGE", instruction="Indoors"))
    assert svc.session.rollbacks == 1


def test_regenerate_rejects_a_draft_that_omits_a_stored_anchor():
    svc, _, _, _, _, _ = service()
    omitted = GeneratedPlanDraft([PlanDraftDay(date(2026, 1, 1), [PlanDraftItem(1, "PLACE", "Other", 2, "10:00", "11:00", "mock")])])
    svc.provider = SimpleNamespace(regenerate_plan=lambda *args: omitted)
    with pytest.raises(AppError) as error:
        svc.regenerate(1, 10, PlanRegenerateRequest(reason="USER_FATIGUE", instruction="Less walking"))
    assert error.value.code == "AI_SCHEMA_VALIDATION_FAILED"


def test_regenerate_runs_temporal_validation_before_replacing_existing_items():
    svc, _, _, rows, revisions, _ = service()
    svc.generation._validate_temporal_draft = lambda days, places: (_ for _ in ()).throw(AppError("EVENT_DATE_MISMATCH", "Event dates do not overlap", 422))

    with pytest.raises(AppError) as error:
        svc.regenerate(1, 10, PlanRegenerateRequest(reason="WEATHER_CHANGE", instruction="Change schedule"))

    assert error.value.code == "EVENT_DATE_MISMATCH"
    assert len(rows) == 1 and rows[0].item_id == 100
    assert revisions == []


def test_confirm_blocks_critical_issues_but_accepts_warning_only():
    svc, plan, _, _, _, issues = service()
    issues.append(SimpleNamespace(severity="CRITICAL", message="Missing place"))
    with pytest.raises(AppError) as error: svc.confirm(1, 10)
    assert error.value.code == "PLAN_HAS_BLOCKING_ISSUES"
    issues[0].severity = "WARNING"
    response = svc.confirm(1, 10)
    assert response.status == "CONFIRMED" and plan.status == "CONFIRMED" and svc.session.commits == 1
