"""Server-side NAVER OAuth authorization-code exchange and profile lookup."""

import json
import socket
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.exceptions import AppError
from app.services.external.auth.provider import SocialIdentity

NAVER_AUTHORIZE_ENDPOINT = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_ENDPOINT = "https://nid.naver.com/oauth2.0/token"
NAVER_PROFILE_ENDPOINT = "https://openapi.naver.com/v1/nid/me"


def _http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    with urlopen(Request(url, headers=headers, method="GET"), timeout=timeout) as response:
        return response.status, response.read()


class NaverOAuthProvider:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, timeout: float,
                 http_get: Callable[[str, dict[str, str], float], tuple[int, bytes]] | None = None):
        self.client_id, self.client_secret, self.redirect_uri, self.timeout = client_id, client_secret, redirect_uri, timeout
        self.http_get = http_get or _http_get

    def authorization_url(self, state: str) -> str:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise AppError("NAVER_AUTH_NOT_CONFIGURED", "NAVER OAuth is not configured", 503)
        return f"{NAVER_AUTHORIZE_ENDPOINT}?{urlencode({'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': self.redirect_uri, 'state': state})}"

    def exchange_code(self, code: str, state: str) -> SocialIdentity:
        if not code.strip() or not state.strip():
            raise AppError("INVALID_NAVER_AUTHORIZATION", "Invalid NAVER authorization response", 401)
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise AppError("NAVER_AUTH_NOT_CONFIGURED", "NAVER OAuth is not configured", 503)
        token_url = f"{NAVER_TOKEN_ENDPOINT}?{urlencode({'grant_type': 'authorization_code', 'client_id': self.client_id, 'client_secret': self.client_secret, 'redirect_uri': self.redirect_uri, 'code': code, 'state': state})}"
        token = self._json(token_url, {})
        access_token = token.get('access_token') if isinstance(token, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise AppError("NAVER_AUTH_ERROR", "NAVER authentication failed", 502)
        return self._profile_identity(access_token)

    def verify_access_token(self, access_token: str) -> SocialIdentity:
        if not isinstance(access_token, str) or not access_token.strip():
            raise AppError("INVALID_NAVER_TOKEN", "Invalid NAVER access token", 401)
        return self._profile_identity(access_token.strip())

    def _profile_identity(self, access_token: str) -> SocialIdentity:
        profile = self._json(NAVER_PROFILE_ENDPOINT, {'Authorization': f'Bearer {access_token}'})
        response = profile.get('response') if isinstance(profile, dict) else None
        provider_user_id = response.get('id') if isinstance(response, dict) else None
        if not isinstance(provider_user_id, str) or not provider_user_id:
            raise AppError("NAVER_AUTH_MALFORMED_RESPONSE", "NAVER returned an invalid profile", 502)
        email = response.get('email') if isinstance(response.get('email'), str) else None
        nickname = response.get('nickname') if isinstance(response.get('nickname'), str) else None
        return SocialIdentity('NAVER', provider_user_id, email, nickname)

    def _json(self, url: str, headers: dict[str, str]) -> dict:
        try:
            status, body = self.http_get(url, headers, self.timeout)
        except (TimeoutError, socket.timeout):
            raise AppError("NAVER_AUTH_TIMEOUT", "NAVER authentication timed out", 504) from None
        except (HTTPError, URLError):
            raise AppError("NAVER_AUTH_NETWORK_ERROR", "NAVER authentication is unavailable", 502) from None
        if status in {400, 401, 403}:
            raise AppError("NAVER_AUTH_ERROR", "NAVER authentication failed", 502)
        if status >= 500:
            raise AppError("NAVER_AUTH_SERVER_ERROR", "NAVER authentication failed", 502)
        try:
            return json.loads(body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise AppError("NAVER_AUTH_MALFORMED_RESPONSE", "NAVER returned an invalid response", 502) from None
