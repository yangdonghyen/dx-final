"""Database and current-user dependencies."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import verify_access_token
from app.db.session import get_db
from app.repositories.user_repository import UserRepository

DBSession = Annotated[Session, Depends(get_db)]

def get_access_claims(authorization: Annotated[str | None, Header()] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError("UNAUTHORIZED", "Authentication required", 401)
    return verify_access_token(authorization.removeprefix("Bearer "))


def get_current_user(claims: Annotated[dict, Depends(get_access_claims)], db: DBSession):
    try: user_id=int(claims["sub"])
    except (ValueError,TypeError): raise AppError("INVALID_TOKEN", "Invalid token", 401) from None
    user=UserRepository(db).get(user_id)
    if user is None: raise AppError("USER_NOT_FOUND", "User not found", 401)
    if user.status != "ACTIVE": raise AppError("USER_INACTIVE", "User is inactive", 403)
    return user
CurrentUser = Annotated[object, Depends(get_current_user)]
