from dataclasses import dataclass
from datetime import timedelta

import pytest

from app.core import security
from app.core.exceptions import AppError
from app.schemas.user import UpdatePreferencesRequest
from app.services.external.auth.provider import SocialIdentity


@dataclass
class MemoryUser:
    user_id: int
    nickname: str | None = None
    age_group: str | None = None
    profile_completed: bool = False
    status: str = "ACTIVE"
    password_hash: str | None = None


@dataclass
class MemoryAuth:
    user_id: int
    provider: str
    provider_user_id: str
    last_login_at: object = None


@dataclass
class MemoryToken:
    user_id: int
    token_hash: str
    expires_at: object
    revoked_at: object = None


class MemorySession:
    def __init__(self):
        self.users, self.auths, self.tokens = {}, {}, {}
        self.preferences, self.interests = {}, {}
        self.codes = {"MUSEUM", "NATURE", "SEA"}
        self.commits = self.rollbacks = 0

    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


class MemoryUsers:
    def __init__(self, session): self.session = session
    def get(self, user_id): return self.session.users.get(user_id)
    def create(self, **fields):
        user = MemoryUser(len(self.session.users) + 1, **fields)
        self.session.users[user.user_id] = user
        return user
    def update(self, user, **fields):
        for field, value in fields.items(): setattr(user, field, value)
        return user


class MemoryAuths:
    def __init__(self, session): self.session = session
    def get(self, provider, provider_user_id): return self.session.auths.get((provider, provider_user_id))
    def create(self, user_id, provider, provider_user_id):
        auth = MemoryAuth(user_id, provider, provider_user_id)
        self.session.auths[(provider, provider_user_id)] = auth
        return auth
    def touch(self, auth, now): auth.last_login_at = now


class MemoryTokens:
    def __init__(self, session): self.session = session
    def create(self, user_id, token_hash, expiry):
        record = MemoryToken(user_id, token_hash, expiry)
        self.session.tokens[token_hash] = record
        return record
    def get(self, token_hash): return self.session.tokens.get(token_hash)
    def revoke(self, record, now): record.revoked_at = now


class MemoryPreferences:
    def __init__(self, session): self.session = session
    def get(self, user_id): return self.session.preferences.get(user_id)
    def get_or_create(self, user_id):
        preference = self.get(user_id)
        if preference is None:
            preference = type("Preference", (), {"walking_tolerance": None, "rest_frequency": None, "avoid_stairs": False, "avoid_hills": False, "taxi_allowed": True, "travel_style": None, "senior_mode": False})()
            self.session.preferences[user_id] = preference
        return preference
    def update(self, preference, **fields):
        for field, value in fields.items(): setattr(preference, field, value)
        return preference


class MemoryInterests:
    def __init__(self, session): self.session = session
    def list_codes(self, user_id): return sorted(self.session.interests.get(user_id, set()))
    def replace(self, user_id, codes): self.session.interests[user_id] = set(codes)


class MemoryInterestCodes:
    def __init__(self, session): self.session = session
    def active_codes(self, codes): return set(codes) & self.session.codes


class StubProvider:
    def __init__(self, identities): self.identities = identities
    def verify(self, provider, access_token): return self.identities[(provider, access_token)]


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "task03-test-secret")


@pytest.fixture
def auth_service(monkeypatch, secret):
    import app.services.auth_service as module
    monkeypatch.setattr(module, "UserRepository", MemoryUsers)
    monkeypatch.setattr(module, "UserAuthRepository", MemoryAuths)
    monkeypatch.setattr(module, "RefreshTokenRepository", MemoryTokens)
    session = MemorySession()
    provider = StubProvider({
        ("KAKAO", "first"): SocialIdentity("KAKAO", "kakao-1", "same@example.com"),
        ("KAKAO", "again"): SocialIdentity("KAKAO", "kakao-1", "same@example.com"),
        ("NAVER", "same-email"): SocialIdentity("NAVER", "naver-1", "same@example.com"),
    })
    return module.AuthService(session, provider), session


@pytest.fixture
def user_service(monkeypatch):
    import app.services.user_service as module
    monkeypatch.setattr(module, "UserRepository", MemoryUsers)
    monkeypatch.setattr(module, "UserPreferenceRepository", MemoryPreferences)
    monkeypatch.setattr(module, "UserInterestRepository", MemoryInterests)
    monkeypatch.setattr(module, "InterestCodeRepository", MemoryInterestCodes)
    session = MemorySession()
    user = MemoryUsers(session).create()
    return module.UserService(session), session, user


def test_access_token_verifies_for_its_subject(secret):
    assert security.verify_access_token(security.create_access_token("42"))["sub"] == "42"


def test_expired_access_token_is_rejected(secret):
    with pytest.raises(AppError, match="expired") as error:
        security.verify_access_token(security._create_token("42", "access", timedelta(seconds=-1)))
    assert error.value.code == "TOKEN_EXPIRED"


def test_tampered_access_token_is_rejected(secret):
    token = security.create_access_token("42")
    tampered = f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}"
    with pytest.raises(AppError) as error: security.verify_access_token(tampered)
    assert error.value.code == "INVALID_TOKEN"


def test_refresh_token_is_rejected_by_access_verifier(secret):
    with pytest.raises(AppError) as error: security.verify_access_token(security.create_refresh_token("42"))
    assert error.value.code == "INVALID_TOKEN"


def test_unknown_token_type_is_rejected(secret):
    with pytest.raises(AppError) as error: security.verify_access_token(security._create_token("42", "unexpected", timedelta(minutes=1)))
    assert error.value.code == "INVALID_TOKEN"


def test_refresh_issues_access_token_for_active_stored_token(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    _, refresh = service._issue(user)
    access, returned_refresh = service.refresh(refresh)
    assert security.verify_access_token(access)["sub"] == str(user.user_id)
    assert returned_refresh == refresh


def test_expired_refresh_token_is_rejected(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    refresh = security._create_token(str(user.user_id), "refresh", timedelta(seconds=-1))
    MemoryTokens(session).create(user.user_id, security.hash_refresh_token(refresh), service._now() + timedelta(days=1))
    with pytest.raises(AppError) as error: service.refresh(refresh)
    assert error.value.code == "TOKEN_EXPIRED"


def test_revoked_refresh_token_is_rejected(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    _, refresh = service._issue(user)
    MemoryTokens(session).get(security.hash_refresh_token(refresh)).revoked_at = service._now()
    with pytest.raises(AppError) as error: service.refresh(refresh)
    assert error.value.code == "INVALID_TOKEN"


def test_refresh_token_not_in_database_is_rejected(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    with pytest.raises(AppError) as error: service.refresh(security.create_refresh_token(str(user.user_id)))
    assert error.value.code == "INVALID_TOKEN"


def test_logout_revokes_refresh_token(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    _, refresh = service._issue(user)
    service.logout(refresh)
    assert MemoryTokens(session).get(security.hash_refresh_token(refresh)).revoked_at is not None
    assert session.commits == 1


def test_logged_out_refresh_token_cannot_be_reused(auth_service):
    service, session = auth_service
    user = MemoryUsers(session).create()
    _, refresh = service._issue(user)
    service.logout(refresh)
    with pytest.raises(AppError) as error: service.refresh(refresh)
    assert error.value.code == "INVALID_TOKEN"


def test_social_relogin_reuses_same_provider_identity_without_new_user(auth_service):
    service, session = auth_service
    first, first_is_new, _, _ = service.social_login("KAKAO", "first")
    again, second_is_new, _, _ = service.social_login("KAKAO", "again")
    assert first_is_new is True and second_is_new is False
    assert again.user_id == first.user_id and len(session.users) == 1


def test_social_accounts_with_same_email_are_not_automatically_linked(auth_service):
    service, session = auth_service
    kakao_user, _, _, _ = service.social_login("KAKAO", "first")
    naver_user, naver_is_new, _, _ = service.social_login("NAVER", "same-email")
    assert naver_is_new is True and naver_user.user_id != kakao_user.user_id
    assert len(session.users) == 2


def test_local_register_hashes_password_and_issues_jwt(auth_service):
    service, session = auth_service
    user, access, refresh = service.register_local("local.user", "correct-password", "Local User")
    assert user.password_hash is not None and "correct-password" not in user.password_hash
    assert security.verify_access_token(access)["sub"] == str(user.user_id)
    assert refresh
    assert session.auths[("LOCAL", "local.user")].user_id == user.user_id


def test_local_login_rejects_duplicate_and_invalid_password(auth_service):
    service, _ = auth_service
    user, _, _ = service.register_local("local.user", "correct-password")
    with pytest.raises(AppError) as duplicate:
        service.register_local("LOCAL.USER", "another-password")
    assert duplicate.value.code == "LOGIN_ID_ALREADY_EXISTS"
    with pytest.raises(AppError) as invalid:
        service.login_local("local.user", "wrong-password")
    assert invalid.value.code == "INVALID_CREDENTIALS"
    logged_in, access, _ = service.login_local("LOCAL.USER", "correct-password")
    assert logged_in.user_id == user.user_id and security.verify_access_token(access)["sub"] == str(user.user_id)


def test_users_me_without_credentials_returns_401_without_database_access(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_duplicate_nicknames_are_allowed(user_service):
    service, session, first = user_service
    second = MemoryUsers(session).create()
    service.update_profile(first, {"nickname": "same-name"})
    service.update_profile(second, {"nickname": "same-name"})
    assert first.nickname == second.nickname == "same-name"


def test_preferences_are_upserted_to_one_record_per_user(user_service):
    service, session, user = user_service
    service.update_preferences(user, UpdatePreferencesRequest(interests=["MUSEUM"]))
    service.update_preferences(user, UpdatePreferencesRequest(avoid_stairs=True))
    assert len(session.preferences) == 1
    assert session.interests[user.user_id] == {"MUSEUM"}
    assert session.preferences[user.user_id].avoid_stairs is True


def test_setup_preferences_update_the_authenticated_users_single_record(user_service):
    service, session, user = user_service
    request = UpdatePreferencesRequest(
        interests=["MUSEUM"], travel_style="SLOW", senior_mode=True
    )

    response = service.update_preferences(user, request)

    assert response.interests == ["MUSEUM"]
    assert response.travel_style == "SLOW"
    assert response.senior_mode is True
    assert len(session.preferences) == 1


def test_sea_and_nature_are_preserved_as_distinct_interest_codes(user_service):
    service, session, user = user_service

    service.update_preferences(user, UpdatePreferencesRequest(interests=["SEA", "NATURE"]))

    assert session.interests[user.user_id] == {"SEA", "NATURE"}


def test_setup_preferences_do_not_modify_another_user(user_service):
    service, session, first_user = user_service
    second_user = MemoryUsers(session).create()
    service.update_preferences(
        second_user,
        UpdatePreferencesRequest(interests=["NATURE"], travel_style="STANDARD"),
    )

    service.update_preferences(
        first_user,
        UpdatePreferencesRequest(interests=["MUSEUM"], senior_mode=True),
    )

    assert session.interests[first_user.user_id] == {"MUSEUM"}
    assert session.interests[second_user.user_id] == {"NATURE"}
    assert session.preferences[second_user.user_id].travel_style == "STANDARD"


def test_unknown_interest_code_is_rejected(user_service):
    service, session, user = user_service
    with pytest.raises(AppError) as error: service.update_preferences(user, UpdatePreferencesRequest(interests=["UNKNOWN"]))
    assert error.value.code == "INVALID_INTEREST_CODE"
    assert session.rollbacks == 1
