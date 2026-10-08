import json
import socket
from urllib.error import URLError

import pytest

from app.core.config import Settings
from app.core.exceptions import AppError
from app.services.external.auth.factory import get_social_auth_provider
from app.services.external.auth.kakao_provider import (
    KAKAO_ACCESS_TOKEN_INFO_ENDPOINT,
    KAKAO_USER_ME_ENDPOINT,
    KakaoSocialAuthProvider,
)
from app.services.external.auth.provider import FakeSocialAuthProvider


def _provider(responses):
    calls = []

    def http_get(url, headers, timeout):
        calls.append((url, headers, timeout))
        return responses[len(calls) - 1]

    return KakaoSocialAuthProvider(2.5, http_get), calls


def test_verifies_kakao_token_then_maps_user_identity():
    provider, calls = _provider([
        (200, json.dumps({"id": 1, "expires_in": 3600}).encode()),
        (200, json.dumps({"id": 12345, "kakao_account": {"email": "user@example.com", "profile": {"nickname": "Kakao User"}}}).encode()),
    ])

    identity = provider.verify("KAKAO", "access-token")

    assert identity.provider == "KAKAO"
    assert identity.provider_user_id == "12345"
    assert identity.email == "user@example.com" and identity.nickname == "Kakao User"
    assert [call[0] for call in calls] == [KAKAO_ACCESS_TOKEN_INFO_ENDPOINT, KAKAO_USER_ME_ENDPOINT]
    assert all(call[1] == {"Authorization": "Bearer access-token"} and call[2] == 2.5 for call in calls)


def test_missing_optional_fields_maps_to_none():
    provider, _ = _provider([
        (200, b'{"id": 1}'),
        (200, b'{"id": 12345, "kakao_account": {}}'),
    ])
    identity = provider.verify("KAKAO", "token")
    assert (identity.provider_user_id, identity.email, identity.nickname) == ("12345", None, None)


@pytest.mark.parametrize(("failure", "code", "status"), [
    ((401, b"{}"), "INVALID_PROVIDER_TOKEN", 401),
    ((200, b"not-json"), "KAKAO_AUTH_MALFORMED_RESPONSE", 502),
    ((200, b"{}"), "KAKAO_AUTH_MALFORMED_RESPONSE", 502),
])
def test_translates_invalid_and_malformed_responses(failure, code, status):
    responses = [failure] if failure[0] == 401 or failure[1] == b"not-json" else [(200, b"{}"), failure]
    provider, _ = _provider(responses)
    with pytest.raises(AppError) as error:
        provider.verify("KAKAO", "token")
    assert (error.value.code, error.value.status_code) == (code, status)


@pytest.mark.parametrize(("http_status", "code"), [
    (500, "KAKAO_AUTH_SERVER_ERROR"),
    (400, "KAKAO_AUTH_ERROR"),
])
def test_translates_non_success_http_statuses(http_status, code):
    provider, _ = _provider([(http_status, b"{}")])
    with pytest.raises(AppError) as error:
        provider.verify("KAKAO", "token")
    assert (error.value.code, error.value.status_code) == (code, 502)


@pytest.mark.parametrize(("failure", "code", "status"), [
    (socket.timeout(), "KAKAO_AUTH_TIMEOUT", 504),
    (URLError("offline"), "KAKAO_AUTH_NETWORK_ERROR", 502),
])
def test_translates_transport_failures(failure, code, status):
    def http_get(*_):
        raise failure

    with pytest.raises(AppError) as error:
        KakaoSocialAuthProvider(1, http_get).verify("KAKAO", "token")
    assert (error.value.code, error.value.status_code) == (code, status)


def test_rejects_non_kakao_provider_and_blank_token_without_http():
    provider = KakaoSocialAuthProvider(1, lambda *_: pytest.fail("must not call HTTP"))
    with pytest.raises(AppError) as error:
        provider.verify("NAVER", "token")
    assert (error.value.code, error.value.status_code) == ("UNSUPPORTED_PROVIDER", 400)
    with pytest.raises(AppError) as error:
        provider.verify("KAKAO", " ")
    assert (error.value.code, error.value.status_code) == ("INVALID_PROVIDER_TOKEN", 401)


def test_fake_provider_and_factory_modes_remain_available():
    assert FakeSocialAuthProvider().verify("KAKAO", "fake:KAKAO:user-1").provider_user_id == "user-1"
    assert isinstance(get_social_auth_provider(Settings(social_auth_provider="fake")), FakeSocialAuthProvider)
    assert isinstance(get_social_auth_provider(Settings(social_auth_provider="real")), KakaoSocialAuthProvider)
