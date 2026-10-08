import json

import pytest

from app.core.exceptions import AppError
from app.services.external.auth.naver_provider import NaverOAuthProvider


def test_exchanges_code_and_maps_naver_provider_id():
    responses = iter([
        (200, json.dumps({"access_token": "provider-token"}).encode()),
        (200, json.dumps({"resultcode": "00", "response": {"id": "naver-unique-id", "email": "same@example.com", "nickname": "Naver User"}}).encode()),
    ])
    provider = NaverOAuthProvider("client-id", "client-secret", "travelmate://auth/naver/callback", 1, lambda *_: next(responses))
    identity = provider.exchange_code("code", "state")
    assert (identity.provider, identity.provider_user_id, identity.email) == ("NAVER", "naver-unique-id", "same@example.com")


def test_rejects_missing_configuration_and_bad_profile():
    with pytest.raises(AppError) as missing:
        NaverOAuthProvider("", "", "", 1).authorization_url("state")
    assert missing.value.code == "NAVER_AUTH_NOT_CONFIGURED"
    provider = NaverOAuthProvider("id", "secret", "uri", 1, lambda *_: (200, b'{"access_token":"token"}'))
    with pytest.raises(AppError) as malformed:
        provider.exchange_code("code", "state")
    assert malformed.value.code == "NAVER_AUTH_MALFORMED_RESPONSE"


def test_verifies_sdk_access_token_from_profile_only():
    provider = NaverOAuthProvider(
        "", "", "", 1,
        lambda _, headers, __: (200, json.dumps({"resultcode": "00", "response": {"id": "sdk-naver-id"}}).encode()),
    )
    identity = provider.verify_access_token("native-sdk-token")
    assert (identity.provider, identity.provider_user_id) == ("NAVER", "sdk-naver-id")


@pytest.mark.parametrize("status,code", [(401, "NAVER_AUTH_ERROR"), (500, "NAVER_AUTH_SERVER_ERROR")])
def test_rejects_invalid_token_and_profile_api_errors(status, code):
    provider = NaverOAuthProvider("", "", "", 1, lambda *_: (status, b"{}"))
    with pytest.raises(AppError) as error:
        provider.verify_access_token("invalid")
    assert error.value.code == code
