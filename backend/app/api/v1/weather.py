from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import CurrentUser
from app.schemas.weather import WeatherResponse
from app.services.external.factory import get_kakao_region_geocoder, get_weather_provider
from app.core.exceptions import AppError
from app.services.weather_service import WeatherService


router = APIRouter(tags=["weather"])


def get_weather_service() -> WeatherService:
    return WeatherService(get_kakao_region_geocoder(), get_weather_provider())


WeatherServiceDependency = Annotated[WeatherService, Depends(get_weather_service)]


@router.get("/weather", response_model=WeatherResponse)
def get_weather(
    user: CurrentUser,
    service: WeatherServiceDependency,
    destination: str | None = Query(default=None, max_length=100),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
) -> WeatherResponse:
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            raise AppError("INVALID_COORDINATES", "lat and lon must be provided together", 400)
        return service.get_weather_at(lat, lon)
    if destination is None or not destination.strip():
        raise AppError("INVALID_DESTINATION", "destination is required when coordinates are absent", 400)
    return service.get_weather(destination)
