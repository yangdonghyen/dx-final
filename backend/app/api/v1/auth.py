from typing import Annotated
from fastapi import APIRouter, Depends
from app.db.session import get_db
from app.schemas.auth import (AuthLoginResponse, AuthUserResponse, LocalLoginRequest,
                              LocalRegisterRequest, LogoutResponse,
                              NaverAuthorizationResponse, NaverLoginRequest,
                              NaverTokenLoginRequest,
                              RefreshTokenRequest, RefreshTokenResponse,
                              SocialLoginRequest, SocialLoginResponse)
from app.services.auth_service import AuthService
from app.services.external.auth.factory import provide_naver_oauth_provider, provide_social_auth_provider

router=APIRouter(tags=["auth"])
def get_provider(): return provide_social_auth_provider()
def get_service(db=Depends(get_db), provider=Depends(get_provider)): return AuthService(db,provider)
Service=Annotated[AuthService,Depends(get_service)]
@router.post("/auth/social-login",response_model=SocialLoginResponse)
def social_login(request:SocialLoginRequest,service:Service):
    user,is_new,access,refresh=service.social_login(request.provider,request.access_token)
    return SocialLoginResponse(access_token=access,refresh_token=refresh,is_new_user=is_new,user=AuthUserResponse(user_id=user.user_id,nickname=user.nickname,profile_completed=user.profile_completed))
def _response(user, access, refresh, is_new_user):
    return AuthLoginResponse(access_token=access, refresh_token=refresh, is_new_user=is_new_user,
        user=AuthUserResponse(user_id=user.user_id, nickname=user.nickname, profile_completed=user.profile_completed))
@router.post('/auth/register', response_model=AuthLoginResponse)
def register(request: LocalRegisterRequest, service: Service):
    user,access,refresh=service.register_local(request.login_id, request.password, request.nickname)
    return _response(user, access, refresh, True)
@router.post('/auth/login', response_model=AuthLoginResponse)
def login(request: LocalLoginRequest, service: Service):
    user,access,refresh=service.login_local(request.login_id, request.password)
    return _response(user, access, refresh, False)
@router.get('/auth/naver/authorize', response_model=NaverAuthorizationResponse)
def naver_authorize(service: Service):
    state=service.create_naver_state()
    return NaverAuthorizationResponse(authorization_url=provide_naver_oauth_provider().authorization_url(state))
@router.post('/auth/naver/login', response_model=AuthLoginResponse)
def naver_login(request: NaverLoginRequest, service: Service):
    service.consume_naver_state(request.state)
    identity=provide_naver_oauth_provider().exchange_code(request.code, request.state)
    user,is_new,access,refresh=service.social_identity_login(identity)
    return _response(user, access, refresh, is_new)
@router.post('/auth/naver/token-login', response_model=AuthLoginResponse)
def naver_token_login(request: NaverTokenLoginRequest, service: Service):
    identity=provide_naver_oauth_provider().verify_access_token(request.access_token)
    user,is_new,access,refresh=service.social_identity_login(identity)
    return _response(user, access, refresh, is_new)
@router.post("/auth/refresh",response_model=RefreshTokenResponse)
def refresh(request:RefreshTokenRequest,service:Service):
    access,raw=service.refresh(request.refresh_token); return RefreshTokenResponse(access_token=access,refresh_token=raw)
@router.post("/auth/logout",response_model=LogoutResponse)
def logout(request:RefreshTokenRequest,service:Service):
    service.logout(request.refresh_token); return LogoutResponse()
