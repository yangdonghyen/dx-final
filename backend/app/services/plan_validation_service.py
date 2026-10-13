from datetime import datetime
from app.repositories.place_repository import PlaceRepository
from app.repositories.plan_repository import PlanItemRepository, PlanValidationIssueRepository
from app.services.place_temporal_validation import (
    event_overlaps_trip,
    is_event_candidate,
    opening_hours_match,
)
from app.services.plan_quality_rules import DayStop, PlanQualityRules, review_plan
class PlanValidationService:
    def __init__(self, session, rules=None): self.session=session; self.items=PlanItemRepository(session); self.places=PlaceRepository(session); self.issues=PlanValidationIssueRepository(session); self.rules=rules
    def validate(self, plan, trip):
        items=self.items.list(plan.plan_id); self.issues.resolve_open(plan.plan_id); findings=[]
        if not items: findings.append((None,"OTHER","CRITICAL","Plan must contain at least one item"))
        seen=set(); by_date={}
        for item in items:
            if trip.start_date and item.visit_date < trip.start_date or trip.end_date and item.visit_date > trip.end_date: findings.append((item,"OTHER","CRITICAL","Item date is outside the trip range"))
            key=(item.visit_date,item.sequence_no)
            if key in seen: findings.append((item,"OTHER","CRITICAL","Duplicate item sequence"))
            seen.add(key); by_date.setdefault(item.visit_date,[]).append(item)
            if item.place_id is not None and self.places.get(item.place_id) is None: findings.append((item,"PLACE_NOT_FOUND","CRITICAL","Referenced place was not found"))
            place = self.places.get(item.place_id) if item.place_id is not None else None
            if place is not None and is_event_candidate(place):
                if event_overlaps_trip(place, item.visit_date, item.visit_date) is not True:
                    findings.append((item,"EVENT_DATE_MISMATCH","CRITICAL","Event dates are unverified or do not match the visit date"))
            if place is not None and opening_hours_match(place, item.visit_date, item.start_time, item.end_time) is False:
                findings.append((item,"OUTSIDE_OPENING_HOURS","CRITICAL","Visit time is outside verified opening hours"))
            elif place is not None and opening_hours_match(place, item.visit_date, item.start_time, item.end_time) is None:
                # Unknown metadata is never treated as an opening-hours fact.
                # Keep the visit, but make the uncertainty visible instead of
                # labelling the item fully VALID.
                findings.append((item,"OPENING_HOURS_UNKNOWN","WARNING","Opening hours are not verified for this visit"))
            if item.start_time and item.end_time and item.end_time < item.start_time: findings.append((item,"TIME_CONFLICT","CRITICAL","Item end time precedes start time"))
        for rows in by_date.values():
            timed=sorted((row for row in rows if row.start_time and row.end_time),key=lambda row:row.start_time)
            for previous,current in zip(timed,timed[1:]):
                if current.start_time < previous.end_time: findings.append((current,"TIME_CONFLICT","CRITICAL","Plan items overlap"))
        findings.extend(self._quality_findings(by_date, trip))
        affected={item.item_id for item,_,_,_ in findings if item is not None}
        for item in items: item.validation_status="WARNING" if item.item_id in affected else "VALID"
        for item,kind,severity,message in findings: self.issues.create(plan.plan_id,item_id=item.item_id if item else None,issue_type=kind,severity=severity,message=message)
        plan.last_validated_at=datetime.utcnow(); return findings

    def _quality_findings(self, by_date, trip):
        """Meal times, food-only days, repeats and stays (WARNING; never blocks a save).

        A plan with any of these is stored as WARNING, never as VALID.
        """
        rules = getattr(self, "rules", None) or PlanQualityRules.from_settings()
        days = []
        rows_by_key = {}
        for visit_date, rows in sorted(by_date.items()):
            label = f"{(visit_date - trip.start_date).days + 1}일차" if getattr(trip, "start_date", None) else visit_date.isoformat()
            stops = []
            for row in rows:
                place = self.places.get(row.place_id) if row.place_id is not None else None
                stops.append(DayStop(row.sequence_no, getattr(row, "item_type", None), row.start_time, row.end_time, place, getattr(row, "travel_minutes_from_previous", None)))
                rows_by_key[(label, row.sequence_no)] = row
            days.append((label, stops))
        return [
            (rows_by_key.get((finding.day, finding.sequence)), finding.issue_type, finding.severity, finding.message)
            for finding in review_plan(days, rules)
        ]

