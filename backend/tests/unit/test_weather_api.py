from app.api.v1.weather import get_weather


class _Service:
    def get_weather_at(self, latitude, longitude):
        return ("coordinates", latitude, longitude)

    def get_weather(self, destination):
        return ("destination", destination)


def test_weather_endpoint_prefers_complete_coordinates_without_geocoding():
    assert get_weather(None, _Service(), destination="부산", lat=35.1796, lon=129.0756) == (
        "coordinates", 35.1796, 129.0756
    )


def test_weather_endpoint_keeps_destination_compatibility():
    assert get_weather(None, _Service(), destination="부산", lat=None, lon=None) == (
        "destination", "부산"
    )
