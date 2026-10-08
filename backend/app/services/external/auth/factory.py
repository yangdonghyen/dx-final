"""Factories for social authentication providers."""

from app.core.config import Settings, get_settings
from app.services.external.auth.kakao_provider import KakaoSocialAuthProvider
from app.services.external.auth.naver_provider import NaverOAuthProvider
from app.services.external.auth.provider import FakeSocialAuthProvider, SocialAuthProvider


def get_social_auth_provider(settings: Settings | None = None) -> SocialAuthProvider:
    settings = settings or get_settings()
    if settings.social_auth_provider == "fake":
        return FakeSocialAuthProvider()
    return KakaoSocialAuthProvider(settings.external_api_timeout_seconds)


def provide_social_auth_provider() -> SocialAuthProvider:
    return get_social_auth_provider()


def get_naver_oauth_provider(settings: Settings | None = None) -> NaverOAuthProvider:
    settings = settings or get_settings()
    return NaverOAuthProvider(
        settings.naver_client_id,
        settings.naver_client_secret.get_secret_value(),
        settings.naver_redirect_uri,
        settings.external_api_timeout_seconds,
    )


def provide_naver_oauth_provider() -> NaverOAuthProvider:
    return get_naver_oauth_provider()
