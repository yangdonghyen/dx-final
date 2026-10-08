from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.session import get_db
from app.schemas.place import PlaceSearchResponse
from app.services.external.factory import provide_place_provider
from app.services.place_search_service import PlaceSearchService

router = APIRouter(tags=["places"])


def get_service(db=Depends(get_db), provider=Depends(provide_place_provider)):
    return PlaceSearchService(db, provider)


Service = Annotated[PlaceSearchService, Depends(get_service)]


@router.get("/places/search", response_model=PlaceSearchResponse)
def search_places(service: Service, query: str = Query(min_length=1, max_length=255), region: str | None = Query(default=None, min_length=1, max_length=100)):
    return PlaceSearchResponse(places=service.search(query, region))
