from dataclasses import dataclass
from typing import Protocol
from app.core.exceptions import AppError
@dataclass(frozen=True)
class SocialIdentity:
    provider: str
    provider_user_id: str
    email: str | None = None
    nickname: str | None = None
class SocialAuthProvider(Protocol):
    def verify(self, provider: str, access_token: str) -> SocialIdentity: ...
class FakeSocialAuthProvider:
    def verify(self, provider: str, access_token: str) -> SocialIdentity:
        if provider not in {"KAKAO", "NAVER"}: raise AppError("UNSUPPORTED_PROVIDER", "Unsupported social provider", 400)
        prefix = f"fake:{provider}:"
        if not access_token.startswith(prefix) or not access_token[len(prefix):].strip(): raise AppError("INVALID_PROVIDER_TOKEN", "Invalid provider token", 401)
        return SocialIdentity(provider, access_token[len(prefix):].strip())
