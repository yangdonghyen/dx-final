"""Kakao route facts adapter with distinct Mobility and Map API contracts."""

import json
import logging
import socket
from time import monotonic
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.external.routing.provider import RouteEstimate


logger = logging.getLogger("app.routing")


KAKAO_MOBILITY_BASE_URL = "https://apis-navi.kakaomobility.com"
KAKAO_MAP_BASE_URL = "https://dapi.kakao.com"
KAKAO_DRIVING_DIRECTIONS_PATH = "/v1/directions"
KAKAO_MAP_WALK_PATH = "/v2/routing/walk"
KAKAO_MAP_PUBLIC_TRANSIT_PATH = "/v2/routing/publictraffic"
WALK_ROUTE_MODES = {"BROAD_FIRST", "SHORTEST", "ACCESSIBLE"}

HttpGet = Callable[[str, dict[str, str], float], tuple[int, bytes]]


def _urlopen_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, bytes]:
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read()


class KakaoMobilityRouteProvider:
    """Return documented Kakao route facts, otherwise ``None``.

    ``CAR`` uses Kakao Mobility Directions. ``PUBLIC_TRANSIT`` uses Kakao Map
    public-traffic routing. ``WALK`` is deliberately an explicit provider
    request because the persisted Trip ``OTHER`` value means an unspecified
    transport method, not walking. ``MIXED`` remains unavailable rather than
    silently choosing a public-transit policy.
    """

    def __init__(
        self,
        api_key: str,
        timeout: float,
        mobility_base_url: str = KAKAO_MOBILITY_BASE_URL,
        map_base_url: str = KAKAO_MAP_BASE_URL,
        walking_route_mode: str = "BROAD_FIRST",
        http_get: HttpGet | None = None,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.mobility_base_url = mobility_base_url.rstrip("/")
        self.map_base_url = map_base_url.rstrip("/")
        self.walking_route_mode = walking_route_mode
        self.http_get = http_get or _urlopen_get

    @staticmethod
    def _coordinates_are_valid(*coordinates: float) -> bool:
        if len(coordinates) != 4 or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in coordinates
        ):
            return False
        origin_latitude, origin_longitude, destination_latitude, destination_longitude = coordinates
        return (
            -90 <= origin_latitude <= 90
            and -90 <= destination_latitude <= 90
            and -180 <= origin_longitude <= 180
            and -180 <= destination_longitude <= 180
        )

    @staticmethod
    def _positive_seconds(value: object) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    @classmethod
    def _driving_route(cls, body: bytes) -> tuple[int, int | None] | None:
        try:
            payload = json.loads(body.decode("utf-8"))
            route = payload["routes"][0]
            if not isinstance(route, dict) or route.get("result_code", 0) != 0:
                return None
            duration = cls._positive_seconds(route["summary"]["duration"])
            if duration is None:
                return None
            return duration, cls._positive_seconds(route["summary"].get("distance"))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
            return None

    def _request(self, base_url: str, path: str, params: dict[str, str]) -> bytes | None:
        if not self.api_key:
            return None
        started = monotonic()
        outcome = "error"
        try:
            status, body = self.http_get(
                f"{base_url}{path}?{urlencode(params)}",
                {"Authorization": f"KakaoAK {self.api_key}"},
                self.timeout,
            )
        except HTTPError:
            return None
        except (URLError, TimeoutError, socket.timeout, OSError):
            return None
        else:
            outcome = "ok" if 200 <= status < 300 else f"http_{status}"
            return body if 200 <= status < 300 else None
        finally:
            # No coordinates, query string, or credential is logged.
            logger.info("route_provider_request path=%s outcome=%s elapsed_ms=%d", path, outcome, (monotonic() - started) * 1000)

    @staticmethod
    def _map_params(
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
    ) -> dict[str, str]:
        # Kakao Map uses WGS84 x=longitude, y=latitude. Set both coordinate
        # systems explicitly so request and documented response are aligned.
        return {
            "start_x": f"{origin_longitude:.12f}",
            "start_y": f"{origin_latitude:.12f}",
            "end_x": f"{destination_longitude:.12f}",
            "end_y": f"{destination_latitude:.12f}",
            "input_coord": "WGS84",
            "output_coord": "WGS84",
        }

    @classmethod
    def _walk_estimate(cls, body: bytes) -> RouteEstimate | None:
        try:
            payload = json.loads(body.decode("utf-8"))
            if payload.get("status") != "OK":
                return None
            properties = payload["route"]["properties"]
            duration = cls._positive_seconds(properties["totalTime"])
            distance = cls._positive_seconds(properties.get("totalDistance"))
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            return None
        return RouteEstimate(duration, "WALK", distance_meters=distance, walking_seconds=duration) if duration is not None else None

    @classmethod
    def _walking_seconds(cls, steps: object) -> int | None:
        """Sum only fully documented WALKING segments; never infer a zero."""
        if not isinstance(steps, list) or not steps:
            return None
        walking_seconds = 0
        walking_steps = 0
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("properties"), dict):
                return None
            properties = step["properties"]
            if not isinstance(properties.get("type"), str):
                return None
            if properties["type"] == "WALKING":
                duration = cls._positive_seconds(properties.get("time"))
                if duration is None:
                    return None
                walking_seconds += duration
                walking_steps += 1
        return walking_seconds if walking_steps else None

    @classmethod
    def _public_transit_estimate(cls, body: bytes) -> RouteEstimate | None:
        try:
            payload = json.loads(body.decode("utf-8"))
            if payload.get("status") != "OK" or not isinstance(payload.get("routes"), list):
                return None
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return None

        # Choose the shortest verified duration, then fewer verified transfers,
        # then source order. This is deterministic for preview comparisons.
        candidates = []
        for index, route in enumerate(payload["routes"]):
            if not isinstance(route, dict) or not isinstance(route.get("properties"), dict):
                continue
            properties = route["properties"]
            duration = cls._positive_seconds(properties.get("totalTime"))
            transfers = properties.get("transfers")
            if duration is None or isinstance(transfers, bool) or not isinstance(transfers, int) or transfers < 0:
                continue
            candidates.append((duration, transfers, index, route))
        if not candidates:
            return None
        duration, transfers, _, route = min(candidates, key=lambda value: value[:3])
        return RouteEstimate(
            duration,
            "PUBLIC_TRANSIT",
            distance_meters=cls._positive_seconds(route["properties"].get("totalDistance")),
            walking_seconds=cls._walking_seconds(route.get("steps")),
            transfer_count=transfers,
        )

    def route(
        self,
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
        transport_mode: str | None,
    ) -> RouteEstimate | None:
        if not self._coordinates_are_valid(
            origin_latitude, origin_longitude, destination_latitude, destination_longitude
        ):
            return None
        if transport_mode == "CAR":
            body = self._request(
                self.mobility_base_url,
                KAKAO_DRIVING_DIRECTIONS_PATH,
                {
                    "origin": f"{origin_longitude:.12f},{origin_latitude:.12f}",
                    "destination": f"{destination_longitude:.12f},{destination_latitude:.12f}",
                    "summary": "true",
                },
            )
            route = self._driving_route(body) if body is not None else None
            return RouteEstimate(route[0], "CAR", distance_meters=route[1]) if route is not None else None
        if transport_mode == "WALK":
            if self.walking_route_mode not in WALK_ROUTE_MODES:
                return None
            params = self._map_params(
                origin_latitude, origin_longitude, destination_latitude, destination_longitude
            )
            params["route_mode"] = self.walking_route_mode
            body = self._request(self.map_base_url, KAKAO_MAP_WALK_PATH, params)
            return self._walk_estimate(body) if body is not None else None
        if transport_mode == "PUBLIC_TRANSIT":
            body = self._request(
                self.map_base_url,
                KAKAO_MAP_PUBLIC_TRANSIT_PATH,
                self._map_params(
                    origin_latitude, origin_longitude, destination_latitude, destination_longitude
                ),
            )
            return self._public_transit_estimate(body) if body is not None else None
        # OTHER is unspecified in the Trip enum; MIXED has no documented route
        # selection policy here. Neither is silently mapped to another mode.
        return None
