"""Create pending regeneration previews without modifying the current itinerary."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.repositories.plan_repository import PlanItemRepository, PlanRegenerationPreviewRepository, PlanRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.plan import PlanRegenerateRequest, PlanRegenerationPreviewResponse
from app.services.plan_generation_service import PlanGenerationService


class PlanRegenerationPreviewService:
    def __init__(self, session, provider, route_provider=None):
        self.session = session; self.provider = provider
        self.plans = PlanRepository(session); self.items = PlanItemRepository(session)
        self.previews = PlanRegenerationPreviewRepository(session); self.trips = TripRepository(session)
        # Candidate discovery can upsert places. A preview may commit only its own row.
        self.generation = PlanGenerationService(session, provider, place_provider=None, route_provider=route_provider)

    def _owned_plan(self, user_id, plan_id):
        plan = self.plans.get(plan_id)
        if plan is None: raise AppError("PLAN_NOT_FOUND", "Plan not found", 404)
        trip = self.trips.get(plan.trip_id)
        if trip is None: raise AppError("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: raise AppError("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED" or plan.status == "ARCHIVED": raise AppError("PLAN_ARCHIVED", "Plan is archived", 400)
        return plan, trip

    @staticmethod
    def _snapshot_item(item) -> dict[str, Any]:
        return {"item_id": item.item_id, "place_id": item.place_id, "visit_date": item.visit_date.isoformat(), "sequence_no": item.sequence_no, "item_type": item.item_type, "title": item.title, "start_time": item.start_time.isoformat() if item.start_time else None, "end_time": item.end_time.isoformat() if item.end_time else None, "validation_status": item.validation_status}

    @staticmethod
    def _proposed_item(item, visit_date, start_time, end_time) -> dict[str, Any]:
        return {"place_id": item.place_id, "visit_date": visit_date.isoformat(), "sequence_no": item.sequence, "item_type": item.item_type, "title": item.title, "start_time": start_time.isoformat() if start_time else None, "end_time": end_time.isoformat() if end_time else None, "recommendation_reason": item.recommendation_reason}

    @staticmethod
    def _validate_no_time_overlap(days) -> None:
        for _, items in days:
            timed = sorted((entry for entry in items if entry[1] and entry[2]), key=lambda entry: entry[1])
            if any(current[1] < previous[2] for previous, current in zip(timed, timed[1:])):
                raise AppError("TIME_CONFLICT", "Preview itinerary items overlap", 422)

    @staticmethod
    def _optional_activity_count(items, candidate_places, anchor_ids):
        """Count non-anchor activity places, excluding known cafes."""
        selected = set()
        anchors = set(anchor_ids)

        for item in items:
            if item.get("item_type") != "PLACE":
                continue

            place_id = item.get("place_id")

            if place_id is None or place_id in anchors:
                continue

            candidate = candidate_places.get(place_id)

            if candidate is None:
                candidate = candidate_places.get(str(place_id))

            if isinstance(candidate, dict):
                category = candidate.get("category")
            else:
                category = getattr(candidate, "category", None)

            category_text = str(category or "").casefold()

            if any(word in category_text for word in (
                "ce7", "cafe", "??", "?????"
            )):
                continue

            selected.add(place_id)

        return len(selected)

    @staticmethod
    def _rest_minutes(items):
        """Measure explicit REST time in minutes."""
        total = 0.0

        for item in items:
            if item.get("item_type") != "REST":
                continue

            start_value = item.get("start_time")
            end_value = item.get("end_time")

            if not isinstance(start_value, str) or not isinstance(end_value, str):
                raise AppError(
                    "FEEDBACK_GOAL_UNVERIFIABLE",
                    "REST time is missing",
                    422,
                )

            try:
                start = datetime.fromisoformat("2000-01-01T" + start_value)
                end = datetime.fromisoformat("2000-01-01T" + end_value)
            except ValueError as exc:
                raise AppError(
                    "FEEDBACK_GOAL_UNVERIFIABLE",
                    "REST time is invalid",
                    422,
                ) from exc

            if start.tzinfo is not None or end.tzinfo is not None or end <= start:
                raise AppError(
                    "FEEDBACK_GOAL_UNVERIFIABLE",
                    "REST time interval is invalid",
                    422,
                )

            total += (end - start).total_seconds() / 60

        return total

    @staticmethod
    def _candidate_value(candidate, name):
        if isinstance(candidate, dict):
            return candidate.get(name)
        return getattr(candidate, name, None)

    @classmethod
    def _route_burden(
        cls, items, candidate_places, route_provider, transport_mode, metric
    ):
        """Sum only facts returned for every scheduled place-to-place leg.

        ``walking_seconds`` and ``duration_seconds`` are intentionally kept
        separate.  Coordinates, a missing provider result, or a partial route
        result are not enough evidence to infer either burden.
        """
        if route_provider is None:
            return None

        by_date = {}
        for item in items:
            place_id = item.get("place_id")
            if place_id is None:
                continue
            visit_date = item.get("visit_date")
            start_value = item.get("start_time")
            place = candidate_places.get(place_id)
            if (
                not isinstance(visit_date, str)
                or not isinstance(start_value, str)
                or place is None
            ):
                return None
            try:
                start = datetime.fromisoformat("2000-01-01T" + start_value)
            except ValueError:
                return None
            latitude = cls._candidate_value(place, "latitude")
            longitude = cls._candidate_value(place, "longitude")
            if latitude is None or longitude is None:
                return None
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                return None
            by_date.setdefault(visit_date, []).append(
                (start, latitude, longitude)
            )

        total = 0
        legs = 0
        for visits in by_date.values():
            visits.sort(key=lambda visit: visit[0])
            for previous, current in zip(visits, visits[1:]):
                try:
                    estimate = route_provider.route(
                        previous[1], previous[2], current[1], current[2],
                        transport_mode,
                    )
                except Exception:
                    return None
                if estimate is None:
                    return None
                value = (
                    getattr(estimate, "walking_seconds", None)
                    if metric == "walking"
                    else getattr(estimate, "duration_seconds", None)
                )
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return None
                total += value
                legs += 1
        return total if legs else None

    @classmethod
    def _validate_feedback_goal(
        cls, current, proposed, feedback_codes,
        candidate_places, anchor_ids, route_provider=None, transport_mode=None,
    ):
        """Verify measurable selected feedback goals."""
        codes = set(feedback_codes)

        if "places" in codes:
            before = cls._optional_activity_count(
                current, candidate_places, anchor_ids
            )
            after = cls._optional_activity_count(
                proposed, candidate_places, anchor_ids
            )

            if before == 0:
                raise AppError(
                    "FEEDBACK_GOAL_UNACHIEVABLE",
                    "No optional activity places are available to remove",
                    422,
                )

            if after >= before:
                raise AppError(
                    "FEEDBACK_GOAL_NOT_MET",
                    "The revised itinerary did not reduce optional activity places",
                    422,
                )

        if "rest" in codes:
            before_rest = cls._rest_minutes(current)
            after_rest = cls._rest_minutes(proposed)

            if after_rest <= before_rest:
                raise AppError(
                    "FEEDBACK_GOAL_NOT_MET",
                    "The revised itinerary did not increase REST time",
                    422,
                )

        for code, metric, description in (
            ("walking", "walking", "walking burden"),
            ("travel", "travel", "travel time"),
        ):
            if code not in codes:
                continue
            before = cls._route_burden(
                current, candidate_places, route_provider, transport_mode, metric
            )
            after = cls._route_burden(
                proposed, candidate_places, route_provider, transport_mode, metric
            )
            # Incomplete directions facts remain UNKNOWN; never estimate from
            # coordinates or reject a preview on an invented comparison.
            if before is not None and after is not None and after >= before:
                raise AppError(
                    "FEEDBACK_GOAL_NOT_MET",
                    f"The revised itinerary did not reduce verified {description}",
                    422,
                )

    @staticmethod
    def _changed(old, new) -> bool:
        return any(old.get(key) != new.get(key) for key in ("visit_date", "start_time", "end_time"))

    def _diff(self, current, proposed):
        remaining, result = list(current), []
        for candidate in proposed:
            if candidate["place_id"] is not None:
                match = next((row for row in remaining if row["place_id"] == candidate["place_id"] and row["item_type"] == candidate["item_type"]), None)
                kind = "ADDED" if match is None else ("RESCHEDULED" if self._changed(match, candidate) else "UNCHANGED")
            else:
                match = next((row for row in remaining if row["place_id"] is None and row["item_type"] in {"REST", "FREE_TIME"} and row["sequence_no"] == candidate["sequence_no"]), None)
                kind = "ADDED" if match is None else ("REST_CHANGED" if self._changed(match, candidate) else "UNCHANGED")
            if match is not None: remaining.remove(match)
            result.append({"change_type": kind, "before": match, "after": candidate})
        result.extend({"change_type": "REMOVED", "before": item, "after": None} for item in remaining)
        return result

    def create(self, user_id, plan_id, request: PlanRegenerateRequest):
        plan, trip = self._owned_plan(user_id, plan_id)
        current = [self._snapshot_item(item) for item in self.items.list(plan.plan_id)]
        try:
            trip_input, preferences, companions, interests, context, candidates, anchor_ids, candidate_places = self.generation._input(trip)
            draft = self.provider.regenerate_plan(trip_input, preferences, companions, interests, context, candidates, request.reason, request.instruction, current, request.feedback_codes)
            draft = self.generation._normalize_draft_dates(draft, trip)
            days = self.generation._validate_draft(self.generation._prepare_draft(draft, candidate_places, anchor_ids, trip), set(candidate_places))
            self._validate_no_time_overlap(days); self.generation._validate_temporal_draft(days, candidate_places)
            self.generation._validate_route_timing(days, candidate_places, trip); self.generation._validate_activity_diversity(days, candidate_places, trip)
            included_anchors = {item.place_id for _, rows in days for item, _, _ in rows if item.place_id is not None}
            if not anchor_ids.issubset(included_anchors): raise self.generation._provider_error()
            proposed_items = [self._proposed_item(item, visit_date, start, end) for visit_date, rows in days for item, start, end in rows]
            if request.reason == "USER_FATIGUE":
                self._validate_feedback_goal(
                    current,
                    proposed_items,
                    request.feedback_codes,
                    candidate_places,
                    anchor_ids,
                    getattr(self.generation, "route_provider", None),
                    getattr(trip, "transport_mode", None),
                )
            preview = self.previews.create(plan_id=plan.plan_id, user_id=user_id, base_version=plan.current_version, reason=request.reason, feedback_codes=list(request.feedback_codes), current_itinerary_snapshot={"items": current}, proposed_itinerary={"items": proposed_items}, diff=self._diff(current, proposed_items), expires_at=datetime.utcnow() + timedelta(minutes=get_settings().plan_regeneration_preview_ttl_minutes))
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise AppError("PREVIEW_STORAGE_UNAVAILABLE", "Preview storage is unavailable", 503) from exc
        except Exception:
            self.session.rollback(); raise
        # Route and opening-hours providers can be unavailable.  Hard failures
        # above are rejected, but do not claim a fully verified itinerary here.
        return PlanRegenerationPreviewResponse(preview_id=preview.preview_id, plan_id=preview.plan_id, base_version=preview.base_version, status=preview.status, proposed_itinerary=preview.proposed_itinerary, diff=preview.diff, validation_status="UNKNOWN", expires_at=preview.expires_at)
