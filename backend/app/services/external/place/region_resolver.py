"""Region filtering policies for place-search providers."""

import json
from pathlib import Path


_GWANGJU = "광주"
_ADMIN_SUFFIXES = ("특별자치시", "특별자치도", "특별시", "광역시", "도", "시", "군", "구")
_GWANGJU_GUS = {"동", "서", "남", "북", "광산"}
_DEFAULT_GWANGJU_GEOJSON = Path(__file__).resolve().parents[4] / "data" / "regions" / "legacy_gwangju_2025.geojson"


def normalize_administrative_name(value: str) -> str:
    """Return an administrative-area name suitable for exact comparison."""
    normalized = value.strip()
    for suffix in _ADMIN_SUFFIXES:
        if normalized.endswith(suffix):
            return normalized[:-len(suffix)]
    return normalized


def parse_address_levels(address: str | None) -> tuple[str, str] | None:
    """Extract the first two whitespace-separated administrative address levels."""
    if not isinstance(address, str):
        return None
    levels = address.split()
    if len(levels) < 2 or not levels[0] or not levels[1]:
        return None
    return levels[0], levels[1]


def parse_region_levels(region: str | None) -> tuple[str, ...] | None:
    """Normalize one or two requested administrative levels without joining them."""
    if not isinstance(region, str):
        return None
    levels = [normalize_administrative_name(level) for level in region.split()[:2]]
    if not levels or any(not level for level in levels):
        return None
    return tuple(levels)


def city_level_region(address: str | None, region: str | None = None) -> str | None:
    """Return the broadest supplied administrative level, without city aliases.

    Kakao addresses place the metropolitan/provincial level first.  This keeps
    an anchor in a district from accidentally turning that district into the
    entire trip search boundary.  Region is only a fallback for legacy records
    that do not have an address.
    """
    levels = parse_address_levels(address)
    if levels is not None:
        return levels[0]
    parsed_region = parse_region_levels(region)
    return parsed_region[0] if parsed_region else None


class RegionResolver:
    """Keeps geographic collection and administrative filtering out of providers."""

    def __init__(self, geojson_path: Path | None = None):
        self.geojson_path = geojson_path or _DEFAULT_GWANGJU_GEOJSON
        self._gwangju_geometry = None
        self._gwangju_bounds = None

    @staticmethod
    def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
        inside = False
        for index, current in enumerate(ring):
            previous = ring[index - 1]
            x1, y1 = previous
            x2, y2 = current
            if (y1 > latitude) != (y2 > latitude):
                crossing = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
                if longitude < crossing:
                    inside = not inside
        return inside

    @staticmethod
    def _polygons(geometry: dict) -> list[list[list[list[float]]]]:
        if geometry.get("type") == "Polygon":
            return [geometry["coordinates"]]
        if geometry.get("type") == "MultiPolygon":
            return geometry["coordinates"]
        raise ValueError("Gwangju geometry must be Polygon or MultiPolygon")

    def _load_gwangju(self):
        if self._gwangju_geometry is not None:
            return self._gwangju_geometry
        payload = json.loads(self.geojson_path.read_text(encoding="utf-8"))
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("Gwangju GeoJSON has no features")
        feature = next((row for row in features if row.get("properties", {}).get("SIDO_CD") == "24"), None)
        if feature is None or not isinstance(feature.get("geometry"), dict):
            raise ValueError("Gwangju GeoJSON feature is missing")
        geometry = feature["geometry"]
        polygons = self._polygons(geometry)
        points = [point for polygon in polygons for ring in polygon for point in ring]
        self._gwangju_bounds = (min(point[0] for point in points), min(point[1] for point in points), max(point[0] for point in points), max(point[1] for point in points))
        self._gwangju_geometry = geometry
        return geometry

    def gwangju_grids(self) -> list[tuple[float, float, float, float]]:
        self._load_gwangju()
        min_x, min_y, max_x, max_y = self._gwangju_bounds
        width, height = (max_x - min_x) / 3, (max_y - min_y) / 3
        return [(min_x + column * width, min_y + row * height, min_x + (column + 1) * width, min_y + (row + 1) * height) for row in range(3) for column in range(3)]

    def in_gwangju(self, longitude: float, latitude: float) -> bool:
        """Retained for GeoJSON smoke tests; administrative filtering does not use it."""
        geometry = self._load_gwangju()
        for polygon in self._polygons(geometry):
            if self._point_in_ring(longitude, latitude, polygon[0]) and not any(self._point_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
                return True
        return False

    @staticmethod
    def _is_gwangju_level1(level1: str) -> bool:
        normalized = normalize_administrative_name(level1)
        return normalized == _GWANGJU or ("광주" in normalized and level1.endswith(("특별시", "광역시")))

    def _matches_region(self, address: str | None, region: str) -> bool:
        levels = parse_address_levels(address)
        requested_levels = parse_region_levels(region)
        if levels is None or requested_levels is None:
            return False
        level1, level2 = levels
        normalized_level1 = normalize_administrative_name(level1)
        normalized_level2 = normalize_administrative_name(level2)
        requested_level1 = requested_levels[0]
        if len(requested_levels) == 2:
            requested_level2 = requested_levels[1]
            if requested_level1 == _GWANGJU:
                return (
                    self._is_gwangju_level1(level1)
                    and requested_level2 == normalized_level2
                )
            return (
                requested_level1 == normalized_level1
                and requested_level2 == normalized_level2
            )
        if requested_level1 == _GWANGJU:
            return self._is_gwangju_level1(level1) and normalized_level2 in _GWANGJU_GUS
        return requested_level1 in {normalized_level1, normalized_level2}

    def matches_region(self, address: str | None, region: str | None) -> bool:
        return isinstance(region, str) and bool(region.strip()) and self._matches_region(address, region)

    def filter(self, candidates, region: str | None):
        if region is None:
            return candidates
        return [candidate for candidate in candidates if self.matches_region(candidate.address, region)]

    def search_query(self, query: str, region: str | None) -> str:
        """Use grids for Gwangju; provide all other regions as a keyword hint."""
        if region is None or normalize_administrative_name(region) == _GWANGJU:
            return query
        return f"{region.strip()} {query}"

    def grid_rectangles(self, region: str | None):
        return self.gwangju_grids() if region is not None and normalize_administrative_name(region) == _GWANGJU else [None]
