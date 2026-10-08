from app.services.external.auth.provider import SocialIdentity
from tests.unit.test_task03_auth_flows import auth_service, secret  # noqa: F401  (fixtures)


def test_new_kakao_user_gets_kakao_nickname(auth_service):
    service, _ = auth_service
    user, *_ = service.social_identity_login(SocialIdentity("KAKAO", "k-1", None, "동현"))
    assert user.nickname == "동현"


def test_existing_user_without_name_is_filled_on_next_login(auth_service):
    service, _ = auth_service
    service.social_identity_login(SocialIdentity("NAVER", "n-1", None, None))
    user, *_ = service.social_identity_login(SocialIdentity("NAVER", "n-1", None, " 동현 "))
    assert user.nickname == "동현"


def test_existing_name_is_not_overwritten_or_cleared(auth_service):
    service, _ = auth_service
    user, *_ = service.social_identity_login(SocialIdentity("KAKAO", "k-2", None, "양동현"))
    again, *_ = service.social_identity_login(SocialIdentity("KAKAO", "k-2", None, "다른이름"))
    blank, *_ = service.social_identity_login(SocialIdentity("KAKAO", "k-2", None, ""))
    assert user.nickname == again.nickname == blank.nickname == "양동현"
