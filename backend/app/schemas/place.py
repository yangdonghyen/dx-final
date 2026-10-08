from decimal import Decimal

from pydantic import BaseModel


class PlaceSearchItemResponse(BaseModel):
    place_id: int
    name: str
    region: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None


class PlaceSearchResponse(BaseModel):
    places: list[PlaceSearchItemResponse]
