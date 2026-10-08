from datetime import time

from app.core.exceptions import AppError
from app.repositories.plan_repository import PlanItemRepository, PlanRepository, PlanRevisionRepository, PlanValidationIssueRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.plan import PlanConfirmResponse, PlanDayResponse, PlanDetailResponse, PlanItemResponse, PlanRegenerateRequest
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_validation_service import PlanValidationService


class PlanRevisionService:
    def __init__(self, session, provider, place_provider=None, route_provider=None):
        self.session = session; self.provider = provider
        self.plans = PlanRepository(session); self.items = PlanItemRepository(session); self.revisions = PlanRevisionRepository(session)
        self.issues = PlanValidationIssueRepository(session); self.trips = TripRepository(session)
        self.generation = PlanGenerationService(session, provider, place_provider, route_provider); self.validation = PlanValidationService(session)

    def _owned_plan(self, user_id, plan_id):
        plan = self.plans.get(plan_id)
        if plan is None: raise AppError("PLAN_NOT_FOUND", "Plan not found", 404)
        trip = self.trips.get(plan.trip_id)
        if trip is None: raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED": raise AppError("TRIP_ARCHIVED", "Trip is archived", 400)
        return plan, trip

    @staticmethod
    def _snapshot_item(item):
        return {"item_id": item.item_id, "place_id": item.place_id, "visit_date": item.visit_date.isoformat(), "sequence_no": item.sequence_no, "item_type": item.item_type, "title": item.title, "start_time": item.start_time.isoformat() if item.start_time else None, "end_time": item.end_time.isoformat() if item.end_time else None, "validation_status": item.validation_status}

    def _response(self, plan, trip):
        grouped = {}
        for item in self.items.list(plan.plan_id): grouped.setdefault(item.visit_date, []).append(item)
        open_issues = self.issues.list_open(plan.plan_id)
        validation_status = "UNKNOWN" if any(issue.severity == "CRITICAL" for issue in open_issues) else ("WARNING" if open_issues else "VALID")
        days = [PlanDayResponse(day=(visit_date - trip.start_date).days + 1 if trip.start_date else index, visit_date=visit_date, items=[PlanItemResponse(item_id=item.item_id, place_id=item.place_id, name=item.title, start_time=item.start_time, end_time=item.end_time, validation_status=item.validation_status) for item in rows]) for index, (visit_date, rows) in enumerate(sorted(grouped.items()), 1)]
        return PlanDetailResponse(plan_id=plan.plan_id, status=plan.status, current_version=plan.current_version, validation_status=validation_status, days=days, warnings=[issue.message for issue in open_issues if issue.severity != "CRITICAL"])

    def get(self, user_id, plan_id):
        plan, trip = self._owned_plan(user_id, plan_id)
        return self._response(plan, trip)

    def regenerate(self, user_id, plan_id, request: PlanRegenerateRequest):
        plan, trip = self._owned_plan(user_id, plan_id)
        if plan.status == "ARCHIVED": raise AppError("PLAN_ARCHIVED", "Plan is archived", 400)
        trip_input, preferences, companions, interests, preference_context, candidates, anchor_ids, candidate_places = self.generation._input(trip)
        current_itinerary = [self._snapshot_item(item) for item in self.items.list(plan.plan_id)]
        draft = self.provider.regenerate_plan(
            trip_input, preferences, companions, interests, preference_context, candidates,
            request.reason, request.instruction, current_itinerary, request.feedback_codes,
        )
        normalizer = getattr(self.generation, "_normalize_draft_dates", None)
        if normalizer is not None:
            draft = normalizer(draft, trip)
            draft = self.generation._prepare_draft(draft, candidate_places, anchor_ids, trip)
        else:
            draft = self.generation._prepare_draft(draft, candidate_places, anchor_ids)
        days = self.generation._validate_draft(draft, set(candidate_places))
        self.generation._validate_temporal_draft(days, candidate_places)
        route_timing_validator = getattr(self.generation, "_validate_route_timing", None)
        if route_timing_validator is not None:
            route_timing_validator(days, candidate_places, trip)
        activity_diversity_validator = getattr(self.generation, "_validate_activity_diversity", None)
        if activity_diversity_validator is not None:
            activity_diversity_validator(days, candidate_places, trip)
        included_anchor_ids = {
            item.place_id
            for _, draft_items in days
            for item, _, _ in draft_items
            if item.place_id is not None
        }
        if not anchor_ids.issubset(included_anchor_ids):
            raise self.generation._provider_error()
        try:
            self.revisions.create(plan.plan_id, revision_no=plan.current_version, revision_type=request.reason, instruction=request.instruction, snapshot={"current_version": plan.current_version, "items": [self._snapshot_item(item) for item in self.items.list(plan.plan_id)]})
            for item in self.items.list(plan.plan_id): self.items.delete(item)
            for visit_date, draft_items in days:
                for draft_item, start_time, end_time in draft_items:
                    self.items.create(plan.plan_id, place_id=draft_item.place_id, visit_date=visit_date, sequence_no=draft_item.sequence, item_type=draft_item.item_type, title=draft_item.title, start_time=start_time, end_time=end_time, recommendation_reason=draft_item.recommendation_reason, validation_status="UNKNOWN")
            findings = self.validation.validate(plan, trip)
            if any(kind == "EVENT_DATE_MISMATCH" for _, kind, _, _ in findings):
                raise AppError("EVENT_DATE_MISMATCH", "Event dates do not match the itinerary", 422)
            if any(kind == "OUTSIDE_OPENING_HOURS" for _, kind, _, _ in findings):
                raise AppError("OUTSIDE_OPENING_HOURS", "Visit time is outside verified opening hours", 422)
            if any(severity == "CRITICAL" for _, _, severity, _ in findings):
                raise self.generation._provider_error()
            plan.current_version += 1
            self.session.commit()
            return self._response(plan, trip)
        except Exception:
            self.session.rollback(); raise

    def confirm(self, user_id, plan_id):
        plan, _ = self._owned_plan(user_id, plan_id)
        if plan.status == "ARCHIVED": raise AppError("PLAN_ARCHIVED", "Plan is archived", 400)
        if any(issue.severity == "CRITICAL" for issue in self.issues.list_open(plan.plan_id)):
            raise AppError("PLAN_HAS_BLOCKING_ISSUES", "Resolve blocking validation issues before confirming", 409)
        try:
            from datetime import datetime
            plan.status = "CONFIRMED"; plan.confirmed_at = datetime.utcnow()
            self.session.commit()
            return PlanConfirmResponse(plan_id=plan.plan_id, status="CONFIRMED")
        except Exception:
            self.session.rollback(); raise
