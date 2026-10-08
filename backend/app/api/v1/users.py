from typing import Annotated
from fastapi import APIRouter, Depends
from app.db.session import get_db
from app.dependencies import CurrentUser
from app.schemas.user import UpdatePreferencesRequest, UpdateUserRequest, UpdateUserResponse, UserMeResponse
from app.services.user_service import UserService

router=APIRouter(tags=["users"])
def get_service(db=Depends(get_db)): return UserService(db)
Service=Annotated[UserService,Depends(get_service)]
@router.get("/users/me",response_model=UserMeResponse)
def get_me(user:CurrentUser,service:Service):
    return UserMeResponse(user_id=user.user_id,nickname=user.nickname,age_group=user.age_group,profile_completed=user.profile_completed,preferences=service.response(user.user_id))
@router.patch("/users/me",response_model=UpdateUserResponse)
def update_me(request:UpdateUserRequest,user:CurrentUser,service:Service):
    value=service.update_profile(user,request.model_dump(exclude_unset=True)); return UpdateUserResponse(user_id=value.user_id,nickname=value.nickname,age_group=value.age_group,profile_completed=value.profile_completed)
@router.patch("/users/me/preferences",response_model=UserMeResponse)
def update_preferences(request:UpdatePreferencesRequest,user:CurrentUser,service:Service):
    prefs=service.update_preferences(user,request); return UserMeResponse(user_id=user.user_id,nickname=user.nickname,age_group=user.age_group,profile_completed=user.profile_completed,preferences=prefs)
