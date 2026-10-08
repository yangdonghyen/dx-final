from datetime import date, time
from types import SimpleNamespace
import pytest
class Session:
    def __init__(self): self.items=[]; self.places={1:object()}; self.issues=[]
    def flush(self): pass
class Items:
    def __init__(self,s): self.s=s
    def list(self,plan_id): return self.s.items
class Places:
    def __init__(self,s): self.s=s
    def get(self,place_id): return self.s.places.get(place_id)
class Issues:
    def __init__(self,s): self.s=s
    def list_open(self,plan_id): return [x for x in self.s.issues if x.resolved_at is None]
    def resolve_open(self,plan_id):
        for x in self.list_open(plan_id): x.resolved_at=object()
    def create(self,plan_id,**fields):
        row=SimpleNamespace(plan_id=plan_id,resolved_at=None,**fields); self.s.issues.append(row); return row
@pytest.fixture
def validation(monkeypatch):
    import app.services.plan_validation_service as mod
    monkeypatch.setattr(mod,'PlanItemRepository',Items); monkeypatch.setattr(mod,'PlaceRepository',Places); monkeypatch.setattr(mod,'PlanValidationIssueRepository',Issues)
    s=Session(); return mod.PlanValidationService(s),s

def item(n,**kw):
    values={'item_id':n,'visit_date':date(2026,1,1),'sequence_no':n,'place_id':1,'start_time':time(10+n),'end_time':time(11+n),'validation_status':'UNKNOWN'}; values.update(kw); return SimpleNamespace(**values)
def run(validation):
    svc,s=validation; plan=SimpleNamespace(plan_id=1,last_validated_at=None); trip=SimpleNamespace(start_date=date(2026,1,1),end_date=date(2026,1,2)); return svc.validate(plan,trip),s,plan

def test_validation_marks_valid_items(validation):
    _,s,plan=run(validation); s.items=[item(1)]; findings=svc=None
    # rerun after fixture data is populated
    findings=validation[0].validate(plan,SimpleNamespace(start_date=date(2026,1,1),end_date=date(2026,1,2)))
    assert findings==[] and s.items[0].validation_status=='VALID' and plan.last_validated_at
@pytest.mark.parametrize('bad,kind',[({'visit_date':date(2025,12,31)},'OTHER'),({'place_id':99},'PLACE_NOT_FOUND'),({'start_time':time(12),'end_time':time(11)},'TIME_CONFLICT')])
def test_validation_records_item_issues(validation,bad,kind):
    svc,s=validation; s.items=[item(1,**bad)]; findings,_,_=run(validation)
    assert any(value[1]==kind for value in findings) and s.items[0].validation_status=='WARNING'
def test_validation_detects_overlap_sequence_and_empty_plan(validation):
    svc,s=validation; s.items=[item(1),item(1,start_time=time(10,30),end_time=time(12))]; findings,_,_=run(validation)
    assert sum(kind=='TIME_CONFLICT' for _,kind,_,_ in findings)==1 and any('Duplicate' in message for *_,message in findings)
    s.items=[]; findings=svc.validate(SimpleNamespace(plan_id=1,last_validated_at=None),SimpleNamespace(start_date=date(2026,1,1),end_date=date(2026,1,2)))
    assert findings[0][1:] == ('OTHER','CRITICAL','Plan must contain at least one item')


def test_final_validation_marks_event_date_mismatch_as_critical(validation):
    svc, s = validation
    event = SimpleNamespace(name="부산불꽃축제", category="축제", event_start_date=date(2026, 11, 7), event_end_date=date(2026, 11, 7))
    s.places[1] = event
    s.items = [item(1, visit_date=date(2026, 10, 23))]

    findings = svc.validate(SimpleNamespace(plan_id=1, last_validated_at=None), SimpleNamespace(start_date=date(2026, 10, 20), end_date=date(2026, 10, 23)))

    assert any(kind == "EVENT_DATE_MISMATCH" and severity == "CRITICAL" for _, kind, severity, _ in findings)


def test_final_validation_marks_verified_hours_mismatch_as_critical(validation):
    svc, s = validation
    s.places[1] = SimpleNamespace(
        name="Museum", category="CULTURE", verification_status="VERIFIED",
        opening_hours={"thursday": {"open": "09:00", "close": "17:00"}},
    )
    s.items = [item(1, visit_date=date(2026, 1, 1), start_time=time(18), end_time=time(19))]

    findings = svc.validate(SimpleNamespace(plan_id=1, last_validated_at=None), SimpleNamespace(start_date=date(2026, 1, 1), end_date=date(2026, 1, 2)))

    assert any(kind == "OUTSIDE_OPENING_HOURS" and severity == "CRITICAL" for _, kind, severity, _ in findings)
