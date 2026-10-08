from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.db.session import get_db
from app.dependencies import CurrentUser
from app.schemas.companion import CompanionCreate, CompanionDeleteResponse, CompanionListResponse, CompanionResponse, CompanionUpdate
from app.services.companion_service import CompanionService

router = APIRouter(tags=["companions"])


def get_service(db=Depends(get_db)):
    return CompanionService(db)


Service = Annotated[CompanionService, Depends(get_service)]


@router.get("/companions", response_model=CompanionListResponse)
def list_companions(user: CurrentUser, service: Service):
    return CompanionListResponse(companions=service.list(user.user_id))


@router.post("/companions", response_model=CompanionResponse, status_code=status.HTTP_201_CREATED)
def create_companion(request: CompanionCreate, user: CurrentUser, service: Service):
    return service.create(user.user_id, request)


@router.patch("/companions/{companion_id}", response_model=CompanionResponse)
def update_companion(companion_id: int, request: CompanionUpdate, user: CurrentUser, service: Service):
    return service.update(user.user_id, companion_id, request)


@router.delete("/companions/{companion_id}", response_model=CompanionDeleteResponse)
def delete_companion(companion_id: int, user: CurrentUser, service: Service):
    service.archive(user.user_id, companion_id)
    return CompanionDeleteResponse()
