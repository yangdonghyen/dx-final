from pathlib import Path

from app.core.exceptions import AppError
from app.services.external.mock_data import load_mock_collection
from app.services.external.place.provider import PlaceCandidate


class MockPlaceProvider:
    """Fixture-backed place search; it never contacts Kakao or TourAPI."""
    def __init__(self, data_dir: Path | None = None): self.data_dir = data_dir

    def search(self, query: str, region: str | None = None) -> list[PlaceCandidate]:
        if not isinstance(query, str) or not query.strip():
            raise AppError("INVALID_PROVIDER_INPUT", "query is required", 400)
        if region is not None and (not isinstance(region, str) or not region.strip()):
            raise AppError("INVALID_PROVIDER_INPUT", "region must not be blank", 400)
        places = load_mock_collection("places.json", "places", {"external_provider", "external_id", "name", "category", "address", "latitude", "longitude", "phone", "source_url"}, self.data_dir)
        needle = query.casefold().strip()
        region_needle = region.casefold().strip() if region else None
        result = [PlaceCandidate(**place) for place in places if needle in " ".join((place["name"], place["category"], place["address"])).casefold()]
        return result if region_needle is None else [place for place in result if region_needle in " ".join((place.name, place.address)).casefold()]

    def search_nearby(self, latitude: float, longitude: float, radius_meters: int, category_codes: list[str], limit_per_category: int) -> list[PlaceCandidate]:
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise AppError("INVALID_PROVIDER_INPUT", "valid coordinates are required", 400)
        if not isinstance(category_codes, list) or not category_codes:
            raise AppError("INVALID_PROVIDER_INPUT", "category_codes are required", 400)
        places = load_mock_collection("places.json", "places", {"external_provider", "external_id", "name", "category", "address", "latitude", "longitude", "phone", "source_url"}, self.data_dir)
        return [PlaceCandidate(**place) for place in places[:limit_per_category * len(category_codes)]]
