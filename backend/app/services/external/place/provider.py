from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlaceCandidate:
    external_provider: str
    external_id: str
    name: str
    category: str
    address: str
    latitude: float
    longitude: float
    phone: str | None
    source_url: str | None
    road_address: str | None = None


class PlaceProvider(Protocol):
    def search(self, query: str, region: str | None = None) -> list[PlaceCandidate]: ...
    def search_nearby(self, latitude: float, longitude: float, radius_meters: int, category_codes: list[str], limit_per_category: int) -> list[PlaceCandidate]: ...
