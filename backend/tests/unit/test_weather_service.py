from datetime import datetime

from app.services.external.weather.kma_provider import (
    KmaForecast,
    condition_from_codes,
    latlon_to_kma_grid,
    latest_short_forecast_base,
    SEOUL,
)
from app.services.weather_service import WeatherService


def test_kma_grid_matches_official_seoul_reference_grid():
    assert latlon_to_kma_grid(37.5665, 126.9780) == (60, 127)


def test_latest_short_forecast_base_uses_previous_issue_before_publication_lag():
    assert latest_short_forecast_base(datetime(2026, 10, 7, 2, 20, tzinfo=SEOUL)) == datetime(2026, 10, 6, 23, 0, tzinfo=SEOUL)
    assert latest_short_forecast_base(datetime(2026, 10, 7, 5, 35, tzinfo=SEOUL)) == datetime(2026, 10, 7, 5, 0, tzinfo=SEOUL)


def test_condition_mapping_prefers_precipitation_over_sky():
    assert condition_from_codes("1", "1") == "비"
    assert condition_from_codes("2", "4") == "비/눈"
    assert condition_from_codes("0", "3") == "구름많음"


class _Geocoder:
    def resolve_region(self, destination):
        assert destination == "부산"
        return 35.1796, 129.0756


class _Provider:
    def short_forecast(self, nx, ny, now):
        assert isinstance(nx, int) and isinstance(ny, int)
        return KmaForecast(
            datetime(2026, 10, 7, 5, tzinfo=SEOUL),
            [
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "TMP", "fcstValue": "19"},
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "PTY", "fcstValue": "1"},
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "SKY", "fcstValue": "4"},
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "POP", "fcstValue": "70"},
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "REH", "fcstValue": "86"},
                {"fcstDate": "20261007", "fcstTime": "0900", "category": "WSD", "fcstValue": "3.4"},
                {"fcstDate": "20261007", "fcstTime": "0000", "category": "TMN", "fcstValue": "16"},
                {"fcstDate": "20261007", "fcstTime": "1200", "category": "TMX", "fcstValue": "21"},
            ],
        )


def test_weather_service_normalizes_only_kma_values():
    result = WeatherService(_Geocoder(), _Provider()).get_weather(
        "부산", datetime(2026, 10, 7, 8, tzinfo=SEOUL)
    )
    assert result.location_name == "부산"
    assert result.current.temperature == 19.0
    assert result.current.condition == "비"
    assert result.current.precipitation_probability == 70
    assert result.current.humidity == 86
    assert result.current.wind_speed == 3.4
    assert result.daily[0].high == 21.0 and result.daily[0].low == 16.0


class _UnusedGeocoder:
    def resolve_region(self, destination):
        raise AssertionError("coordinate weather must not call Kakao")


def test_coordinate_weather_bypasses_destination_geocoding():
    result = WeatherService(_UnusedGeocoder(), _Provider()).get_weather_at(
        35.1796, 129.0756, datetime(2026, 10, 7, 8, tzinfo=SEOUL)
    )
    assert result.location_name == "현재 위치"
