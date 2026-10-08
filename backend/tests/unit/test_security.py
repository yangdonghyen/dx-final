import pytest
from app.core.security import create_access_token, create_refresh_token, get_jwt_settings, hash_refresh_token, verify_access_token

def test_jwt_settings_are_read_without_generating_a_secret(monkeypatch):
    monkeypatch.setenv("JWT_ACCESS_EXPIRE_MINUTES", "45")
    settings = get_jwt_settings()
    assert settings.access_expire_minutes == 45
    assert settings.refresh_expire_days == 14
    assert settings.secret_key.get_secret_value() == ""

def test_signed_tokens_verify_and_refresh_hashes_are_one_way(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")
    access = create_access_token("42")
    assert verify_access_token(access)["sub"] == "42"
    assert hash_refresh_token("raw-token") != "raw-token"
    with pytest.raises(Exception):
        verify_access_token(create_refresh_token("42"))