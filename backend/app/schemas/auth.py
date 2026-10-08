from typing import Literal
from pydantic import BaseModel, Field

class SocialLoginRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=20)
    access_token: str = Field(min_length=1, max_length=4096)
class LocalRegisterRequest(BaseModel):
    login_id: str = Field(min_length=3, max_length=255, pattern=r"^[A-Za-z0-9._@+-]+$")
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, min_length=1, max_length=50)
class LocalLoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)
class NaverAuthorizationResponse(BaseModel):
    authorization_url: str
class NaverLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=255)
class NaverTokenLoginRequest(BaseModel):
    access_token: str = Field(min_length=1, max_length=4096)
class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
class AuthUserResponse(BaseModel):
    user_id: int
    nickname: str | None
    profile_completed: bool
class SocialLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    is_new_user: bool
    user: AuthUserResponse
class AuthLoginResponse(SocialLoginResponse):
    pass
class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
class LogoutResponse(BaseModel):
    message: Literal["logout_success"] = "logout_success"
