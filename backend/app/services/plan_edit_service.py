from datetime import date, datetime, timedelta
from app.core.exceptions import AppError
from app.repositories.place_repository import PlaceRepository
from app.repositories.plan_repository import PlanItemRepository, PlanRepository, PlanRevisionRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.plan import PlanDayResponse, PlanEditResponse, PlanItemResponse
from app.services.plan_travel_time import EMPTY_TRAVEL, travel_response_fields, travel_statuses
from app.services.plan_validation_service import PlanValidationService

class PlanEditService:
    def __init__(self, session):
        self.session = session; self.plans = PlanRepository(session); self.items = PlanItemRepository(session)
        self.revisions = PlanRevisionRepository(session); self.places = PlaceRepository(session); self.trips = TripRepository(session)
        self.validation = PlanValidationService(session)
    def _fail(self, code, message, status=400): raise AppError(code, message, status)
    def _owned_plan(self, user_id, plan_id):
        plan = self.plans.get(plan_id)
        if plan is None: self._fail("PLAN_NOT_FOUND", "Plan not found", 404)
        trip = self.trips.get(plan.trip_id)
        if trip is None: self._fail("TRIP_NOT_FOUND", "Trip not found", 404)
        if trip.user_id != user_id: self._fail("FORBIDDEN", "You do not own this trip", 403)
        if trip.status == "ARCHIVED": self._fail("TRIP_ARCHIVED", "Trip is archived")
        return plan, trip
    def _item(self, plan_id, item_id):
        if item_id is None: self._fail("INVALID_EDIT_PAYLOAD", "item_id is required", 422)
        item = self.items.get(item_id)
        if item is None: self._fail("PLAN_ITEM_NOT_FOUND", "Plan item not found", 404)
        if item.plan_id != plan_id: self._fail("PLAN_ITEM_PLAN_MISMATCH", "Plan item belongs to another plan")
        return item
    @staticmethod
    def _serialize(item):
        return {"item_id": item.item_id, "place_id": item.place_id, "visit_date": item.visit_date.isoformat(), "sequence_no": item.sequence_no, "item_type": item.item_type, "title": item.title, "start_time": item.start_time.isoformat() if item.start_time else None, "end_time": item.end_time.isoformat() if item.end_time else None, "transport_mode_from_previous": item.transport_mode_from_previous, "travel_minutes_from_previous": item.travel_minutes_from_previous, "travel_distance_meters_from_previous": item.travel_distance_meters_from_previous, "recommendation_reason": item.recommendation_reason, "validation_status": item.validation_status}
    def _revision(self, plan):
        snapshot = {"current_version": plan.current_version, "items": [self._serialize(item) for item in self.items.list(plan.plan_id)]}
        self.revisions.create(plan.plan_id, revision_no=plan.current_version, revision_type="USER_EDIT", instruction=None, snapshot=snapshot)
    def _day_items(self, plan_id, visit_date): return [item for item in self.items.list(plan_id) if item.visit_date == visit_date]
    def _set_order(self, rows):
        if not rows: return
        offset = max(row.sequence_no for row in rows) + len(rows) + 1
        for index, row in enumerate(rows, 1): row.sequence_no = offset + index
        self.session.flush()
        for index, row in enumerate(rows, 1): row.sequence_no = index
        self.session.flush()
    def _clear_travel(self, plan_id, visit_date):
        # Stored legs are no longer the day's legs after a place or order change.
        for row in self._day_items(plan_id, visit_date):
            for field, value in EMPTY_TRAVEL.items(): setattr(row, field, value)
        self.session.flush()
    def _delete(self, plan, request):
        item = self._item(plan.plan_id, request.item_id); visit_date = item.visit_date
        self.items.delete(item); self._set_order(self._day_items(plan.plan_id, visit_date)); self._clear_travel(plan.plan_id, visit_date)
    def _replace(self, plan, request):
        item = self._item(plan.plan_id, request.item_id)
        if request.new_place_id is None: self._fail("INVALID_EDIT_PAYLOAD", "new_place_id is required", 422)
        place = self.places.get(request.new_place_id)
        if place is None: self._fail("PLACE_NOT_FOUND", "Place not found", 404)
        self.items.update(item, place_id=place.place_id, title=place.name, item_type="PLACE"); self._clear_travel(plan.plan_id, item.visit_date)
    def _visit_date(self, trip, day):
        if trip.start_date is None: self._fail("INVALID_EDIT_PAYLOAD", "Trip start_date is required", 422)
        visit_date = trip.start_date + timedelta(days=day - 1)
        if trip.end_date is not None and visit_date > trip.end_date: self._fail("INVALID_EDIT_PAYLOAD", "day is outside the trip range", 422)
        return visit_date
    def _add_rest(self, plan, trip, request):
        if request.day is None or request.after_item_id is None or request.duration_minutes is None: self._fail("INVALID_EDIT_PAYLOAD", "day, after_item_id and duration_minutes are required", 422)
        visit_date = self._visit_date(trip, request.day); after = self._item(plan.plan_id, request.after_item_id)
        if after.visit_date != visit_date: self._fail("INVALID_EDIT_PAYLOAD", "after_item_id does not belong to the requested day", 422)
        if after.end_time is None: self._fail("INVALID_EDIT_PAYLOAD", "after_item_id must have an end_time", 422)
        finish = datetime.combine(date.min, after.end_time) + timedelta(minutes=request.duration_minutes)
        if finish.date() != date.min: self._fail("INVALID_EDIT_PAYLOAD", "Rest duration exceeds the day", 422)
        later = sorted((item for item in self._day_items(plan.plan_id, visit_date) if item.sequence_no > after.sequence_no), key=lambda item: item.sequence_no, reverse=True)
        for item in later: item.sequence_no += 1
        self.session.flush()
        self.items.create(plan.plan_id, place_id=None, visit_date=visit_date, sequence_no=after.sequence_no + 1, item_type="REST", title="Rest", start_time=after.end_time, end_time=finish.time(), validation_status="UNKNOWN")
    def _reorder(self, plan, trip, request):
        if request.day is None or request.item_ids is None: self._fail("INVALID_EDIT_PAYLOAD", "day and item_ids are required", 422)
        if len(request.item_ids) != len(set(request.item_ids)): self._fail("INVALID_EDIT_PAYLOAD", "item_ids must not contain duplicates", 422)
        rows = self._day_items(plan.plan_id, self._visit_date(trip, request.day)); by_id = {item.item_id: item for item in rows}
        ordered = [by_id.get(item_id) for item_id in request.item_ids]
        if any(item is None for item in ordered) or set(request.item_ids) != set(by_id): self._fail("INVALID_EDIT_PAYLOAD", "item_ids must contain every item for the requested day", 422)
        self._set_order(ordered); self._clear_travel(plan.plan_id, ordered[0].visit_date if ordered else None)
    def _response(self, plan, trip, findings):
        grouped = {}
        for item in self.items.list(plan.plan_id): grouped.setdefault(item.visit_date, []).append(item)
        days = []
        for index, (visit_date, rows) in enumerate(sorted(grouped.items()), 1):
            day = (visit_date - trip.start_date).days + 1 if trip.start_date else index
            statuses = travel_statuses(rows)
            days.append(PlanDayResponse(day=day, visit_date=visit_date, items=[PlanItemResponse(item_id=item.item_id, place_id=item.place_id, name=item.title, start_time=item.start_time, end_time=item.end_time, validation_status=item.validation_status, **travel_response_fields(item, statuses[id(item)])) for item in rows]))
        return PlanEditResponse(plan_id=plan.plan_id, status=plan.status, current_version=plan.current_version, days=days, warnings=[message for _, _, severity, message in findings if severity != "CRITICAL"])
    def edit(self, user_id, plan_id, request):
        plan, trip = self._owned_plan(user_id, plan_id)
        try:
            self._revision(plan)
            if request.operation == "DELETE_PLACE": self._delete(plan, request)
            elif request.operation == "REPLACE_PLACE": self._replace(plan, request)
            elif request.operation == "ADD_REST": self._add_rest(plan, trip, request)
            elif request.operation == "REORDER": self._reorder(plan, trip, request)
            else: self._fail("INVALID_EDIT_OPERATION", "Unsupported edit operation", 422)
            findings = self.validation.validate(plan, trip); plan.current_version += 1
            self.session.commit(); return self._response(plan, trip, findings)
        except Exception:
            self.session.rollback(); raise
