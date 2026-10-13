"""Routing boundary for itinerary planning.

Providers return only facts obtained from a directions service.  A missing
result is deliberately different from a zero-minute journey: callers must not
estimate route durations or transit details from coordinates.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RouteEstimate:
    duration_seconds: int
    mode: str
    # Route distance as returned by the directions provider, in metres.  It is
    # optional because a valid provider response is allowed to omit distance.
    distance_meters: int | None = None
    walking_seconds: int | None = None
    transfer_count: int | None = None


class RouteProvider(Protocol):
    def route(
        self,
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
        transport_mode: str | None,
    ) -> RouteEstimate | None: ...


class UnavailableRouteProvider:
    """Safe default until a licensed directions/transit adapter is configured."""

    def route(
        self,
        origin_latitude: float,
        origin_longitude: float,
        destination_latitude: float,
        destination_longitude: float,
        transport_mode: str | None,
    ) -> RouteEstimate | None:
        return None
