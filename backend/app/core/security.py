"""Minimal, dependency-free HS256 JWT helpers for authentication."""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import SecretStr

from app.core.config import get_settings
from app.core.exceptions import AppError


@dataclass(frozen=True)
class JWTSettings:
    secret_key: SecretStr
    access_expire_minutes: int
    refresh_expire_days: int


def get_jwt_settings() -> JWTSettings:
    settings = get_settings()
    return JWTSettings(settings.jwt_secret_key, settings.jwt_access_expire_minutes, settings.jwt_refresh_expire_days)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _secret() -> bytes:
    secret = get_jwt_settings().secret_key.get_secret_value()
    if not secret:
        raise AppError("INVALID_TOKEN", "Token service is not configured", 401)
    return secret.encode("utf-8")


def _create_token(subject: str, token_type: str, expires_in: timedelta) -> str:
    now = datetime.now(UTC)
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": str(subject), "type": token_type, "iat": int(now.timestamp()), "exp": int((now + expires_in).timestamp()), "jti": secrets.token_urlsafe(16)}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{_b64encode(hmac.new(_secret(), message, hashlib.sha256).digest())}"


def create_access_token(subject: str) -> str:
    return _create_token(subject, "access", timedelta(minutes=get_jwt_settings().access_expire_minutes))


def create_refresh_token(subject: str) -> str:
    return _create_token(subject, "refresh", timedelta(days=get_jwt_settings().refresh_expire_days))


def _verify_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = _b64encode(hmac.new(_secret(), f"{header}.{payload}".encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        decoded = json.loads(_b64decode(payload))
        if decoded.get("type") != expected_type or not isinstance(decoded.get("sub"), str):
            raise AppError("INVALID_TOKEN", "Invalid token", 401)
        if int(decoded["exp"]) <= int(datetime.now(UTC).timestamp()):
            raise AppError("TOKEN_EXPIRED", "Token has expired", 401)
        return decoded
    except AppError:
        raise
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        raise AppError("INVALID_TOKEN", "Invalid token", 401) from None


def verify_access_token(token: str) -> dict[str, Any]:
    return _verify_token(token, "access")


def verify_refresh_token(token: str) -> dict[str, Any]:
    return _verify_token(token, "refresh")


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
