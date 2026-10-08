from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from app.core.exceptions import AppError
from app.schemas.weather import CurrentWeatherResponse, DailyWeatherResponse, WeatherResponse
from app.services.external.weather.kma_provider import SEOUL, KmaProvider, condition_from_codes, latlon_to_kma_grid


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


class WeatherService:
    def __init__(self, geocoder, provider: KmaProvider):
        self.geocoder = geocoder
        self.provider = provider

    def get_weather(self, destination: str, now: datetime | None = None) -> WeatherResponse:
        clean_destination = destination.strip() if isinstance(destination, str) else ""
        if not clean_destination:
            raise AppError("INVALID_DESTINATION", "destination is required", 400)
        latitude, longitude = self.geocoder.resolve_region(clean_destination)
        nx, ny = latlon_to_kma_grid(latitude, longitude)
        forecast = self.provider.short_forecast(nx, ny, now)
        return self._normalize(clean_destination, forecast.base_at, forecast.items, now)

    def get_weather_at(
        self,
        latitude: float,
        longitude: float,
        now: datetime | None = None,
    ) -> WeatherResponse:
        try:
            nx, ny = latlon_to_kma_grid(latitude, longitude)
        except (TypeError, ValueError):
            raise AppError("INVALID_COORDINATES", "valid latitude and longitude are required", 400) from None
        forecast = self.provider.short_forecast(nx, ny, now)
        return self._normalize("현재 위치", forecast.base_at, forecast.items, now)

    @staticmethod
    def _normalize(destination: str, base_at: datetime, items: list[dict], now: datetime | None) -> WeatherResponse:
        grouped: dict[tuple[date, str], dict[str, object]] = defaultdict(dict)
        for item in items:
            try:
                when = datetime.strptime(f"{item['fcstDate']}{item['fcstTime']}", "%Y%m%d%H%M").replace(tzinfo=SEOUL)
                category, value = item["category"], item["fcstValue"]
            except (KeyError, TypeError, ValueError):
                continue
            if category in {"TMP", "TMN", "TMX", "SKY", "PTY", "POP", "REH", "WSD"}:
                grouped[(when.date(), when.strftime("%H%M"))][category] = value
        if not grouped:
            raise AppError("KMA_MALFORMED_RESPONSE", "KMA forecast contains no supported weather values", 502)

        current_time = (now or datetime.now(SEOUL)).astimezone(SEOUL)
        ordered = sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
        current_values = next((values for (day, time), values in ordered if datetime.combine(day, datetime.strptime(time, "%H%M").time(), tzinfo=SEOUL) >= current_time), ordered[0][1])
        current = CurrentWeatherResponse(
            temperature=_number(current_values.get("TMP")),
            condition=condition_from_codes(str(current_values.get("PTY")) if current_values.get("PTY") is not None else None, str(current_values.get("SKY")) if current_values.get("SKY") is not None else None),
            precipitation_probability=_integer(current_values.get("POP")),
            humidity=_integer(current_values.get("REH")),
            wind_speed=_number(current_values.get("WSD")),
        )

        days: dict[date, list[dict[str, object]]] = defaultdict(list)
        for (day, _), values in ordered:
            days[day].append(values)
        daily = []
        for day, values_list in sorted(days.items()):
            merged = {key: value for values in values_list for key, value in values.items() if key in {"TMN", "TMX"}}
            noon = next((values for (entry_day, entry_time), values in ordered if entry_day == day and entry_time >= "1200"), values_list[0])
            daily.append(DailyWeatherResponse(
                date=day,
                condition=condition_from_codes(str(noon.get("PTY")) if noon.get("PTY") is not None else None, str(noon.get("SKY")) if noon.get("SKY") is not None else None),
                high=_number(merged.get("TMX")), low=_number(merged.get("TMN")),
            ))
        return WeatherResponse(location_name=destination, forecast_base_at=base_at, current=current, daily=daily)
