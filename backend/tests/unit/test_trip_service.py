from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.schemas.trip import TripCreate, TripPreferenceInput, TripUpdate


@dataclass
class Trip:
    trip_id: int
    user_id: int
    title: str | None = None
    departure: str | None = None
    destination: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_krw: int | None = None
    transport_mode: str | None = None
    status: str = "DRAFT"


@dataclass
class Interest:
    interest_code: str
    source_type: str
    is_confirmed: bool


class Session:
    def __init__(self):
        self.trips, self.trip_preferences, self.trip_companions, self.trip_interests = {}, {}, {}, {}
        self.user_preference = SimpleNamespace(walking_tolerance="LOW", rest_frequency="HIGH", avoid_stairs=True, avoid_hills=False, taxi_allowed=True, travel_style="SLOW")
        self.user_interest_codes = ["FOOD"]
        self.companions = {1: SimpleNamespace(companion_id=1, user_id=1, name="Mother", relation="MOTHER", age_group="60S", status="ACTIVE"), 2: SimpleNamespace(companion_id=2, user_id=2, name="Other", relation="FRIEND", age_group="30S", status="ACTIVE"), 3: SimpleNamespace(companion_id=3, user_id=1, name="Archived", relation="FATHER", age_group="60S", status="ARCHIVED")}
        self.companion_preferences = {1: SimpleNamespace(walking_tolerance="VERY_LOW", rest_frequency="NORMAL", avoid_stairs=True, avoid_hills=True, taxi_allowed=False), 2: SimpleNamespace(walking_tolerance=None, rest_frequency=None, avoid_stairs=False, avoid_hills=False, taxi_allowed=True), 3: SimpleNamespace(walking_tolerance=None, rest_frequency=None, avoid_stairs=False, avoid_hills=False, taxi_allowed=True)}
        self.companion_interests = {1: ["NATURE"], 2: ["CAFE"], 3: ["HISTORY"]}
        self.codes = {"FOOD", "CAFE", "NATURE", "CULTURE", "HISTORY", "SHOPPING", "EXHIBITION", "ACTIVITY", "SEA", "CITY", "REST"}
        self.commits = self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self):
        self.rollbacks += 1
        self.trips.clear(); self.trip_preferences.clear(); self.trip_companions.clear(); self.trip_interests.clear()


class Trips:
    def __init__(self, s): self.s=s
    def get(self, trip_id): return self.s.trips.get(trip_id)
    def list_active_for_user(self, user_id): return [trip for trip in self.s.trips.values() if trip.user_id == user_id and trip.status != "ARCHIVED"]
    def create(self, user_id, **fields):
        trip=Trip(len(self.s.trips)+1, user_id, **fields); self.s.trips[trip.trip_id]=trip; return trip
    def update(self, trip, **fields):
        for key,value in fields.items(): setattr(trip,key,value)
        return trip


class TripPreferences:
    def __init__(self,s): self.s=s
    def get(self,trip_id): return self.s.trip_preferences.get(trip_id)
    def create(self,trip_id,**fields):
        value=SimpleNamespace(**fields); self.s.trip_preferences[trip_id]=value; return value
    def update(self,value,**fields):
        for key,item in fields.items(): setattr(value,key,item)
        return value


class TripCompanions:
    def __init__(self,s): self.s=s
    def list(self,trip_id): return self.s.trip_companions.get(trip_id,[])
    def create(self,trip_id,**fields):
        value=SimpleNamespace(**fields); self.s.trip_companions.setdefault(trip_id,[]).append(value); return value
    def remove_not_in(self,trip_id,ids): self.s.trip_companions[trip_id]=[item for item in self.list(trip_id) if item.companion_id in ids]


class TripInterests:
    def __init__(self,s): self.s=s
    def list(self,trip_id): return sorted(self.s.trip_interests.get(trip_id,[]), key=lambda item:item.interest_code)
    def create(self,trip_id,interest_code,source_type,is_confirmed):
        value=Interest(interest_code,source_type,is_confirmed); self.s.trip_interests.setdefault(trip_id,[]).append(value); return value
    def remove_user_and_codes(self,trip_id,codes): self.s.trip_interests[trip_id]=[item for item in self.list(trip_id) if item.source_type != "USER" and item.interest_code not in codes]


class TripSelectedPlaces:
    def __init__(self,s): self.s=s
    def list(self,trip_id): return []


class UserPreferences:
    def __init__(self,s): self.s=s
    def get(self,user_id): return self.s.user_preference
class UserInterests:
    def __init__(self,s): self.s=s
    def list_codes(self,user_id): return list(self.s.user_interest_codes)
class Companions:
    def __init__(self,s): self.s=s
    def get(self,companion_id): return self.s.companions.get(companion_id)
class CompanionPreferences:
    def __init__(self,s): self.s=s
    def get(self,companion_id): return self.s.companion_preferences.get(companion_id)
class CompanionInterests:
    def __init__(self,s): self.s=s
    def list_codes(self,companion_id): return list(self.s.companion_interests.get(companion_id,[]))
class Codes:
    def __init__(self,s): self.s=s
    def active_codes(self,codes): return set(codes)&self.s.codes


@pytest.fixture
def trip_service(monkeypatch):
    import app.services.trip_service as module
    monkeypatch.setattr(module,"TripRepository",Trips); monkeypatch.setattr(module,"TripPreferenceRepository",TripPreferences)
    monkeypatch.setattr(module,"TripCompanionRepository",TripCompanions); monkeypatch.setattr(module,"TripInterestRepository",TripInterests)
    monkeypatch.setattr(module,"TripSelectedPlaceRepository",TripSelectedPlaces)
    monkeypatch.setattr(module,"UserPreferenceRepository",UserPreferences); monkeypatch.setattr(module,"UserInterestRepository",UserInterests)
    monkeypatch.setattr(module,"CompanionRepository",Companions); monkeypatch.setattr(module,"CompanionPreferenceRepository",CompanionPreferences)
    monkeypatch.setattr(module,"CompanionInterestRepository",CompanionInterests); monkeypatch.setattr(module,"InterestCodeRepository",Codes)
    session=Session(); return module.TripService(session),session


def request(**overrides):
    values={"title":"Seoul trip","departure":"Gwangju","destination":"Seoul","start_date":"2026-10-10","end_date":"2026-10-12","budget_krw":300000,"transport_mode":"PUBLIC_TRANSIT","companion_ids":[1],"trip_preferences":{"rest_frequency":"LOW"},"interest_codes":["CAFE"]}
    values.update(overrides); return TripCreate(**values)


def test_trip_endpoints_require_authentication(client):
    assert client.get("/api/v1/trips").status_code == 401
    assert client.post("/api/v1/trips",json={}).status_code == 401


def test_create_snapshots_user_preferences_companion_and_interests(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    assert trip.status=="DRAFT" and session.trip_preferences[trip.trip_id].rest_frequency=="LOW"
    assert session.trip_preferences[trip.trip_id].travel_style == "SLOW"
    snapshot=session.trip_companions[trip.trip_id][0]
    assert snapshot.name_snapshot=="Mother" and snapshot.interests_snapshot==["NATURE"]
    assert [(item.interest_code,item.source_type) for item in session.trip_interests[trip.trip_id]]==[("CAFE","USER")]


@pytest.mark.parametrize("travel_style", ["SLOW", "STANDARD", "FOOD_FOCUSED"])
def test_explicit_trip_travel_style_overrides_profile_and_is_trip_scoped(trip_service, travel_style):
    service, session = trip_service

    trip = service.create(1, request(trip_preferences={"rest_frequency": "LOW", "travel_style": travel_style}))

    assert session.trip_preferences[trip.trip_id].travel_style == travel_style
    assert session.user_preference.travel_style == "SLOW"


def test_trip_preference_input_rejects_unknown_travel_style():
    with pytest.raises(ValueError):
        TripPreferenceInput(travel_style="RELAXED")


def test_user_interest_overrides_same_profile_interest_source(trip_service):
    service,session=trip_service; trip=service.create(1,request(interest_codes=["FOOD"]))
    assert [(item.interest_code,item.source_type) for item in session.trip_interests[trip.trip_id]]==[("FOOD","USER")]


def test_trip_interest_snapshot_uses_only_explicit_selection_and_never_profile_sea(trip_service):
    service, session = trip_service
    session.user_interest_codes = ["SEA", "FOOD"]

    city_trip = service.create(1, request(interest_codes=["CITY"]))
    empty_trip = service.create(1, request(interest_codes=[]))
    sea_trip = service.create(1, request(interest_codes=["SEA"]))

    assert [item.interest_code for item in session.trip_interests[city_trip.trip_id]] == ["CITY"]
    assert session.trip_interests.get(empty_trip.trip_id, []) == []
    assert [item.interest_code for item in session.trip_interests[sea_trip.trip_id]] == ["SEA"]


def test_city_only_request_parsing_snapshot_and_plan_interest_context_are_preserved(trip_service):
    from app.services.plan_generation_service import PlanGenerationService
    from app.services.exaone_interest_normalizer import (
        normalize_exaone_interest_codes,
        raw_exaone_interest_codes,
    )

    service, session = trip_service
    session.user_interest_codes = ["SEA"]
    trip = service.create(1, request(destination="Busan", interest_codes=["city"]))
    snapshot_codes = [
        row.interest_code for row in session.trip_interests[trip.trip_id]
    ]

    assert snapshot_codes == ["CITY"]
    assert raw_exaone_interest_codes(snapshot_codes) == ["CITY"]
    assert normalize_exaone_interest_codes(snapshot_codes) == []

    anchor = SimpleNamespace(
        place_id=163, name="Anchor", category="AT4", region="Busan",
        address="Busan Suyeong-gu", latitude=35.15, longitude=129.11,
    )
    city_candidate = SimpleNamespace(
        place_id=170, name="City museum", category="CT1", region="Busan",
        address="Busan Jung-gu", latitude=35.10, longitude=129.03,
        event_start_date=None, event_end_date=None,
    )
    generator = PlanGenerationService.__new__(PlanGenerationService)
    generator._stored_anchors = lambda current_trip: [anchor]
    generator.preferences = SimpleNamespace(get=lambda trip_id: None)
    generator._candidate_places = lambda scope, anchors, preferences: [anchor, city_candidate]
    generator.companions = SimpleNamespace(list=lambda trip_id: [])
    generator.interests = TripInterests(session)

    _, _, _, canonical, context, candidates, _, _ = generator._input(trip)

    assert canonical == []
    assert context == {"raw_interest_codes": ["CITY"]}
    assert [candidate["place_id"] for candidate in candidates] == [163, 170]


def test_explicit_trip_style_is_read_by_plan_generation_input(trip_service):
    from app.services.plan_generation_service import PlanGenerationService

    service, session = trip_service
    trip = service.create(1, request(trip_preferences={"travel_style": "SLOW"}))
    anchor = SimpleNamespace(
        place_id=163, name="Anchor", category="AT4", region="Busan",
        address="Busan Suyeong-gu", latitude=35.15, longitude=129.11,
    )
    generator = PlanGenerationService.__new__(PlanGenerationService)
    generator._stored_anchors = lambda current_trip: [anchor]
    generator.preferences = SimpleNamespace(get=lambda trip_id: session.trip_preferences[trip_id])
    generator._candidate_places = lambda scope, anchors, preferences: [anchor]
    generator.companions = SimpleNamespace(list=lambda trip_id: [])
    generator.interests = TripInterests(session)

    _, preferences, _, _, _, _, _, _ = generator._input(trip)

    assert preferences["travel_style"] == "SLOW"


def test_cafe_and_rest_interest_snapshots_reach_plan_input_without_profile_mutation(trip_service):
    from app.services.exaone_interest_normalizer import normalize_exaone_interest_codes, raw_exaone_interest_codes

    service, session = trip_service
    trip = service.create(1, request(interest_codes=["CAFE", "REST"]))
    stored_codes = [row.interest_code for row in session.trip_interests[trip.trip_id]]

    assert stored_codes == ["CAFE", "REST"]
    assert normalize_exaone_interest_codes(stored_codes) == ["CAFE"]
    assert raw_exaone_interest_codes(stored_codes) == ["REST"]
    assert session.user_interest_codes == ["FOOD"]


def test_new_trip_snapshot_does_not_retain_sea_after_it_is_deselected(trip_service):
    service, session = trip_service
    old_trip = service.create(1, request(interest_codes=["SEA"]))
    new_trip = service.create(1, request(interest_codes=["FOOD"]))

    assert [item.interest_code for item in session.trip_interests[old_trip.trip_id]] == ["SEA"]
    assert [item.interest_code for item in session.trip_interests[new_trip.trip_id]] == ["FOOD"]


def test_snapshot_is_independent_from_later_source_changes(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    session.user_preference.rest_frequency="NORMAL"; session.user_preference.travel_style="FOOD_FOCUSED"; session.companions[1].name="Changed"; session.companion_interests[1]=["CAFE"]
    detail=service.detail(1,trip.trip_id)
    assert detail.preferences.rest_frequency=="LOW" and detail.preferences.travel_style == "SLOW"
    assert detail.companions[0].name=="Mother" and detail.companions[0].interests==["NATURE"]


def test_unknown_interest_and_invalid_companions_are_rejected_before_creation(trip_service):
    service,session=trip_service
    with pytest.raises(AppError,match="Invalid interest"): service.create(1,request(interest_codes=["UNKNOWN"]))
    with pytest.raises(AppError) as other: service.create(1,request(companion_ids=[2]))
    assert other.value.code=="FORBIDDEN" and not session.trips
    with pytest.raises(AppError) as archived: service.create(1,request(companion_ids=[3]))
    assert archived.value.code=="COMPANION_ARCHIVED"


def test_list_is_owned_and_excludes_archived(trip_service):
    service,session=trip_service; first=service.create(1,request()); archived=service.create(1,request(title="Old")); service.create(2,request(companion_ids=[]))
    session.trips[archived.trip_id].status="ARCHIVED"
    assert [item.trip_id for item in service.list(1)]==[first.trip_id]


def test_detail_other_user_and_missing_trip_are_not_exposed(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    with pytest.raises(AppError) as forbidden: service.detail(2,trip.trip_id)
    with pytest.raises(AppError) as missing: service.detail(1,999)
    assert forbidden.value.code=="FORBIDDEN" and missing.value.code=="TRIP_NOT_FOUND"


def test_patch_updates_only_explicit_fields_and_validates_dates(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    detail=service.update(1,trip.trip_id,TripUpdate(budget_krw=400000,transport_mode="CAR"))
    assert detail.budget_krw==400000 and detail.transport_mode=="CAR" and detail.destination=="Seoul"
    with pytest.raises(ValueError,match="end_date"): TripUpdate(start_date="2026-10-12",end_date="2026-10-10")


def test_trip_primary_walk_mode_is_persisted_and_legacy_modes_remain_distinct(trip_service):
    service, session = trip_service
    walk_trip = service.create(1, request(transport_mode="WALK"))
    other_trip = service.create(1, request(transport_mode="OTHER"))
    mixed_trip = service.create(1, request(transport_mode="MIXED"))

    assert walk_trip.transport_mode == "WALK"
    assert other_trip.transport_mode == "OTHER"
    assert mixed_trip.transport_mode == "MIXED"
    assert service.update(1, other_trip.trip_id, TripUpdate(transport_mode="WALK")).transport_mode == "WALK"


def test_patch_preference_and_new_companion_snapshot(trip_service):
    service,session=trip_service; trip=service.create(1,request(companion_ids=[]))
    detail=service.update(1,trip.trip_id,TripUpdate(companion_ids=[1],trip_preferences=TripPreferenceInput(avoid_hills=True)))
    assert detail.preferences.avoid_hills is True and detail.companions[0].name=="Mother"


def test_patch_user_interests_updates_user_set_without_refreshing_sources(trip_service):
    service,session=trip_service; trip=service.create(1,request(interest_codes=["CAFE"]))
    detail=service.update(1,trip.trip_id,TripUpdate(interest_codes=["FOOD","NATURE"]))
    assert [(item.interest_code,item.source_type) for item in detail.interests]==[("FOOD","USER"),("NATURE","USER")]


def test_delete_archives_and_preserves_snapshots(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    service.archive(1,trip.trip_id)
    assert session.trips[trip.trip_id].status=="ARCHIVED" and service.list(1)==[]
    assert trip.trip_id in session.trip_preferences and session.trip_companions[trip.trip_id] and session.trip_interests[trip.trip_id]


def test_other_user_cannot_modify_or_archive_trip(trip_service):
    service,session=trip_service; trip=service.create(1,request())
    with pytest.raises(AppError) as update: service.update(2,trip.trip_id,TripUpdate(title="No"))
    with pytest.raises(AppError) as archive: service.archive(2,trip.trip_id)
    assert update.value.code==archive.value.code=="FORBIDDEN"


def test_duplicate_request_relationships_are_rejected():
    with pytest.raises(ValueError,match="unique"): TripCreate(companion_ids=[1,1])
    with pytest.raises(ValueError,match="unique"): TripCreate(interest_codes=["food","FOOD"])



def test_snapshot_failure_rolls_back_all_trip_rows(trip_service, monkeypatch):
    service, session = trip_service
    def fail_snapshot(*args, **kwargs):
        raise RuntimeError("snapshot write failed")
    monkeypatch.setattr(service.trip_companions, "create", fail_snapshot)
    with pytest.raises(RuntimeError, match="snapshot write failed"):
        service.create(1, request())
    assert session.rollbacks == 1
    assert not session.trips and not session.trip_preferences and not session.trip_companions and not session.trip_interests

