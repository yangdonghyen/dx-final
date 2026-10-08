"""Kakao access-token verification adapter.

The bearer token is deliberately used only in HTTP headers and is never logged.
"""

import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.exceptions import AppError
from app.services.external.auth.provider import SocialIdentity


KAKAO_ACCESS_TOKEN_INFO_ENDPOINT = "https://kapi.kakao.com/v1/user/access_token_info"
KAKAO_USER_ME_ENDPOINT = "https://kapi.kakao.com/v2/user/me"

HttpGet = Callable[[str, dict[str, str], float], tuple[int, bytes]]


def _urlopen_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


class KakaoSocialAuthProvider:
    def __init__(self, timeout: float, http_get: HttpGet | None = None) -> None:
        self.timeout = timeout
        self.http_get = http_get or _urlopen_get

    def verify(self, provider: str, access_token: str) -> SocialIdentity:
        if provider != "KAKAO":
            raise AppError("UNSUPPORTED_PROVIDER", "Unsupported social provider", 400)
        if not isinstance(access_token, str) or not access_token.strip():
            raise AppError("INVALID_PROVIDER_TOKEN", "Invalid provider token", 401)

        headers = {"Authorization": f"Bearer {access_token}"}
        self._get_json(KAKAO_ACCESS_TOKEN_INFO_ENDPOINT, headers)
        user = self._get_json(KAKAO_USER_ME_ENDPOINT, headers)

        try:
            user_id = user["id"]
            if user_id is None:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise AppError(
                "KAKAO_AUTH_MALFORMED_RESPONSE",
                "Kakao returned an invalid authentication response",
                502,
            ) from None

        account = user.get("kakao_account") if isinstance(user, dict) else None
        email = account.get("email") if isinstance(account, dict) else None
        profile = account.get("profile") if isinstance(account, dict) else None
        nickname = profile.get("nickname") if isinstance(profile, dict) else None
        return SocialIdentity(
            provider="KAKAO",
            provider_user_id=str(user_id),
            email=email if isinstance(email, str) else None,
            nickname=nickname if isinstance(nickname, str) else None,
        )

    def _get_json(self, url: str, headers: dict[str, str]) -> dict:
        try:
            status, body = self.http_get(url, headers, self.timeout)
        except HTTPError as error:
            status, body = error.code, b""
        except (TimeoutError, socket.timeout):
            raise AppError("KAKAO_AUTH_TIMEOUT", "Kakao authentication timed out", 504) from None
        except (URLError, OSError):
            raise AppError("KAKAO_AUTH_NETWORK_ERROR", "Kakao authentication is unavailable", 502) from None

        if status == 401:
            raise AppError("INVALID_PROVIDER_TOKEN", "Invalid provider token", 401)
        if status >= 500:
            raise AppError("KAKAO_AUTH_SERVER_ERROR", "Kakao authentication failed", 502)
        if status < 200 or status >= 300:
            raise AppError("KAKAO_AUTH_ERROR", "Kakao authentication failed", 502)
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise AppError(
                "KAKAO_AUTH_MALFORMED_RESPONSE",
                "Kakao returned an invalid authentication response",
                502,
            ) from None
