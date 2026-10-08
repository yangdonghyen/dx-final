"""Apply or cancel a persisted preview; never call an AI provider here."""

from datetime import date, datetime, time

from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppError
from app.repositories.plan_repository import PlanItemRepository, PlanRegenerationPreviewRepository, PlanRepository, PlanRevisionRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.plan import PlanRegenerationPreviewApplyResponse
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_regeneration_preview_service import PlanRegenerationPreviewService


class PlanRegenerationApprovalService:
    def __init__(self, session, provider, route_provider=None):
        self.session = session
        self.plans = PlanRepository(session); self.previews = PlanRegenerationPreviewRepository(session)
        self.items = PlanItemRepository(session); self.revisions = PlanRevisionRepository(session); self.trips = TripRepository(session)
        self.generation = PlanGenerationService(session, provider, place_provider=None, route_provider=route_provider)

    def _locked_owned(self, user_id, plan_id, preview_id):
        # Every writer uses this order to avoid inverse Plan/Preview locking.
        plan = self.plans.get_for_update(plan_id)
        if plan is None: raise AppError("PLAN_NOT_FOUND", "Plan not found", 404)
        trip = self.trips.get(plan.trip_id)
        if trip is None: raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this trip", 403)
        preview = self.previews.get_for_update(preview_id)
        if preview is None or preview.plan_id != plan.plan_id: raise AppError("PREVIEW_NOT_FOUND", "Preview not found", 404)
        if preview.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this preview", 403)
        return plan, trip, preview

    @staticmethod
    def _snapshot(item):
        return PlanRegenerationPreviewService._snapshot_item(item)

    def _draft(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise self.generation._provider_error()
        by_date = {}
        for raw in payload["items"]:
            try:
                visit_date = date.fromisoformat(raw["visit_date"])
                item = PlanDraftItem(raw["sequence_no"], raw["item_type"], raw["title"], raw.get("place_id"), raw.get("start_time"), raw.get("end_time"), raw.get("recommendation_reason", ""))
            except (KeyError, TypeError, ValueError):
                raise self.generation._provider_error() from None
            by_date.setdefault(visit_date, []).append(item)
        return GeneratedPlanDraft([PlanDraftDay(visit_date, items) for visit_date, items in sorted(by_date.items())])

    def _validate_stored_draft(self, draft, trip, candidate_places, anchor_ids):
        expected_dates = self.generation._date_skeleton(trip)
        if [day.visit_date for day in draft.days] != expected_dates:
            raise self.generation._provider_error()
        used = set()
        for day in draft.days:
            for item in day.items:
                if item.place_id is None:
                    if item.item_type not in {"REST", "FREE_TIME"}: raise self.generation._provider_error()
                    continue
                place = candidate_places.get(item.place_id)
                if place is None or item.place_id in used: raise self.generation._provider_error()
                if item.title != place.name or item.item_type != self.generation._canonical_item_type(place):
                    raise self.generation._provider_error()
                used.add(item.place_id)
        days = self.generation._validate_draft(draft, set(candidate_places))
        PlanRegenerationPreviewService._validate_no_time_overlap(days)
        self.generation._validate_temporal_draft(days, candidate_places)
        self.generation._validate_route_timing(days, candidate_places, trip)
        self.generation._validate_activity_diversity(days, candidate_places, trip)
        included = {item.place_id for _, rows in days for item, _, _ in rows if item.place_id is not None}
        if not anchor_ids.issubset(included): raise self.generation._provider_error()
        return days

    def approve(self, user_id, plan_id, preview_id):
        try:
            plan, trip, preview = self._locked_owned(user_id, plan_id, preview_id)
            if preview.status != "PENDING": raise AppError("PREVIEW_NOT_PENDING", "Preview is no longer pending", 409)
            if self.previews.is_expired(preview, datetime.utcnow()): raise AppError("PREVIEW_EXPIRED", "Preview has expired", 409)
            if preview.base_version != plan.current_version: raise AppError("PREVIEW_VERSION_CONFLICT", "Plan changed after preview creation", 409)
            current = [self._snapshot(item) for item in self.items.list(plan.plan_id)]
            if preview.current_itinerary_snapshot != {"items": current}: raise AppError("PREVIEW_STALE", "Current itinerary no longer matches preview", 409)
            _, _, _, _, _, _, anchor_ids, candidate_places = self.generation._input(trip)
            days = self._validate_stored_draft(self._draft(preview.proposed_itinerary), trip, candidate_places, anchor_ids)
            self.revisions.create(plan.plan_id, revision_no=plan.current_version, revision_type=preview.reason, instruction=None, snapshot={"current_version": plan.current_version, "items": current})
            for item in self.items.list(plan.plan_id): self.items.delete(item)
            for visit_date, rows in days:
                for item, start, end in rows:
                    self.items.create(plan.plan_id, place_id=item.place_id, visit_date=visit_date, sequence_no=item.sequence, item_type=item.item_type, title=item.title, start_time=start, end_time=end, recommendation_reason=item.recommendation_reason, validation_status="UNKNOWN")
            plan.current_version += 1
            self.previews.set_status(preview, "APPLIED", applied_at=datetime.utcnow())
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise AppError("PREVIEW_STORAGE_UNAVAILABLE", "Preview storage is unavailable", 503) from exc
        except Exception:
            self.session.rollback(); raise
        return PlanRegenerationPreviewApplyResponse(preview_id=preview.preview_id, plan_id=plan.plan_id, status="APPLIED", current_version=plan.current_version, approved=True)

    def cancel(self, user_id, plan_id, preview_id):
        try:
            plan, _, preview = self._locked_owned(user_id, plan_id, preview_id)
            if preview.status != "PENDING": raise AppError("PREVIEW_NOT_PENDING", "Preview is no longer pending", 409)
            self.previews.set_status(preview, "CANCELLED")
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise AppError("PREVIEW_STORAGE_UNAVAILABLE", "Preview storage is unavailable", 503) from exc
        except Exception:
            self.session.rollback(); raise
        return PlanRegenerationPreviewApplyResponse(preview_id=preview.preview_id, plan_id=plan.plan_id, status="CANCELLED")
