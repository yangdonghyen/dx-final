from datetime import date, datetime

from pydantic import BaseModel


class CurrentWeatherResponse(BaseModel):
    temperature: float | None = None
    condition: str | None = None
    precipitation_probability: int | None = None
    humidity: int | None = None
    wind_speed: float | None = None


class DailyWeatherResponse(BaseModel):
    date: date
    condition: str | None = None
    high: float | None = None
    low: float | None = None


class WeatherResponse(BaseModel):
    location_name: str
    forecast_base_at: datetime
    current: CurrentWeatherResponse
    daily: list[DailyWeatherResponse]
