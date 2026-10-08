from dataclasses import dataclass

import pytest

from app.core.exceptions import AppError
from app.schemas.companion import CompanionCreate, CompanionPreferenceInput, CompanionUpdate


@dataclass
class Companion:
    companion_id: int
    user_id: int
    name: str
    relation: str
    age_group: str | None
    status: str = "ACTIVE"


@dataclass
class Preference:
    companion_id: int
    walking_tolerance: str | None = None
    rest_frequency: str | None = None
    avoid_stairs: bool = False
    avoid_hills: bool = False
    taxi_allowed: bool = True


class Session:
    def __init__(self):
        self.companions, self.preferences, self.interests = {}, {}, {}
        self.codes = {"FOOD", "CAFE", "NATURE", "CULTURE", "HISTORY", "SHOPPING", "EXHIBITION", "ACTIVITY"}
        self.commits = self.rollbacks = 0

    def commit(self): self.commits += 1
    def rollback(self):
        self.rollbacks += 1
        self.companions.clear()
        self.preferences.clear()
        self.interests.clear()


class Companions:
    def __init__(self, session): self.session = session
    def get(self, companion_id): return self.session.companions.get(companion_id)
    def list_active_for_user(self, user_id):
        return [item for item in self.session.companions.values() if item.user_id == user_id and item.status == "ACTIVE"]
    def create(self, user_id, **fields):
        companion = Companion(len(self.session.companions) + 1, user_id, **fields)
        self.session.companions[companion.companion_id] = companion
        return companion
    def update(self, companion, **fields):
        for field, value in fields.items(): setattr(companion, field, value)
        return companion


class Preferences:
    def __init__(self, session): self.session = session
    def for_companions(self, ids): return {item_id: self.session.preferences[item_id] for item_id in ids}
    def get(self, companion_id): return self.session.preferences.get(companion_id)
    def create(self, companion_id, **fields):
        preference = Preference(companion_id, **fields)
        self.session.preferences[companion_id] = preference
        return preference
    def update(self, preference, **fields):
        for field, value in fields.items(): setattr(preference, field, value)
        return preference


class Interests:
    def __init__(self, session): self.session = session
    def for_companions(self, ids): return {item_id: sorted(self.session.interests.get(item_id, set())) for item_id in ids}
    def list_codes(self, companion_id): return sorted(self.session.interests.get(companion_id, set()))
    def replace(self, companion_id, codes): self.session.interests[companion_id] = set(codes)


class Codes:
    def __init__(self, session): self.session = session
    def active_codes(self, codes): return set(codes) & self.session.codes


@pytest.fixture
def companion_service(monkeypatch):
    import app.services.companion_service as module
    monkeypatch.setattr(module, "CompanionRepository", Companions)
    monkeypatch.setattr(module, "CompanionPreferenceRepository", Preferences)
    monkeypatch.setattr(module, "CompanionInterestRepository", Interests)
    monkeypatch.setattr(module, "InterestCodeRepository", Codes)
    session = Session()
    return module.CompanionService(session), session


def create_request(**overrides):
    data = {
        "name": "Mother", "relation": "MOTHER", "age_group": "60S",
        "preferences": {"interests": ["NATURE", "FOOD"], "walking_tolerance": "LOW", "rest_frequency": "HIGH", "avoid_stairs": True, "avoid_hills": False, "taxi_allowed": True},
    }
    data.update(overrides)
    return CompanionCreate(**data)


def test_companion_endpoints_require_authentication(client):
    assert client.get("/api/v1/companions").status_code == 401
    assert client.post("/api/v1/companions", json={}).status_code == 401


def test_create_companion_includes_preference_and_interests(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    assert created.companion_id == 1 and created.name == "Mother"
    assert created.preferences.interests == ["NATURE", "FOOD"]
    assert created.preferences.walking_tolerance == "LOW"
    assert session.commits == 1 and len(session.preferences) == 1


def test_unknown_interest_code_is_rejected_without_partial_companion(companion_service):
    service, session = companion_service
    with pytest.raises(AppError) as error:
        service.create(1, create_request(preferences={"interests": ["UNKNOWN"]}))
    assert error.value.code == "INVALID_INTEREST_CODE"
    assert not session.companions and not session.preferences and not session.interests


def test_list_only_returns_own_active_companions(companion_service):
    service, session = companion_service
    first = service.create(1, create_request())
    archived = service.create(1, create_request(name="Archived"))
    service.create(2, create_request(name="Other user"))
    session.companions[archived.companion_id].status = "ARCHIVED"
    companions = service.list(1)
    assert [item.companion_id for item in companions] == [first.companion_id]
    assert companions[0].preferences.interests == ["FOOD", "NATURE"]


def test_patch_basic_fields_preserves_unprovided_values(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    updated = service.update(1, created.companion_id, CompanionUpdate(name="Renamed"))
    assert updated.name == "Renamed"
    assert updated.relation == "MOTHER" and updated.preferences.interests == ["FOOD", "NATURE"]


def test_patch_preference_fields(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    updated = service.update(1, created.companion_id, CompanionUpdate(preferences=CompanionPreferenceInput(avoid_hills=True, taxi_allowed=False)))
    assert updated.preferences.avoid_hills is True and updated.preferences.taxi_allowed is False
    assert updated.preferences.walking_tolerance == "LOW"


def test_patch_interests_replaces_entire_set(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    updated = service.update(1, created.companion_id, CompanionUpdate(preferences=CompanionPreferenceInput(interests=["CAFE"])))
    assert updated.preferences.interests == ["CAFE"]


def test_other_user_cannot_update_companion(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    with pytest.raises(AppError) as error: service.update(2, created.companion_id, CompanionUpdate(name="Nope"))
    assert error.value.code == "FORBIDDEN"


def test_updating_missing_companion_returns_not_found(companion_service):
    service, session = companion_service
    with pytest.raises(AppError) as error: service.update(1, 999, CompanionUpdate(name="Nope"))
    assert error.value.code == "COMPANION_NOT_FOUND"


def test_delete_archives_and_preserves_preference_and_interests(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    service.archive(1, created.companion_id)
    assert session.companions[created.companion_id].status == "ARCHIVED"
    assert created.companion_id in session.preferences and created.companion_id in session.interests
    assert service.list(1) == []


def test_other_user_cannot_archive_companion(companion_service):
    service, session = companion_service
    created = service.create(1, create_request())
    with pytest.raises(AppError) as error: service.archive(2, created.companion_id)
    assert error.value.code == "FORBIDDEN"


def test_duplicate_companion_interest_is_rejected_by_request_validation():
    with pytest.raises(ValueError, match="unique"):
        CompanionPreferenceInput(interests=["FOOD", "food"])
