from types import SimpleNamespace

import app.services.external.factory as factory
from app.core.config import Settings
from app.services.external.routing import CachedRouteProvider, RouteEstimate, UnavailableRouteProvider
from tests.unit.test_plan_generation_service import Place, service  # noqa: F401  (pytest fixture)

A = (35.1587, 129.1604)
B = (35.1532, 129.1187)
C = (35.0975, 129.0106)


class CountingRoutes:
    def __init__(self, results=None, default=RouteEstimate(600, "CAR")):
        self.results = results or {}
        self.default = default
        self.calls = []

    def route(self, *args):
        self.calls.append(args)
        return self.results.get(args, self.default)


def leg(origin, destination, mode="CAR"):
    return (*origin, *destination, mode)


def test_same_leg_three_times_calls_provider_once():
    inner = CountingRoutes()
    provider = CachedRouteProvider(inner)

    results = [provider.route(*leg(A, B)) for _ in range(3)]

    assert results == [RouteEstimate(600, "CAR")] * 3
    assert len(inner.calls) == 1


def test_reverse_direction_and_other_mode_are_separate_legs():
    inner = CountingRoutes()
    provider = CachedRouteProvider(inner)

    provider.route(*leg(A, B))
    provider.route(*leg(B, A))
    provider.route(*leg(A, B, "PUBLIC_TRANSIT"))
    provider.route(*leg(B, A))

    assert inner.calls == [leg(A, B), leg(B, A), leg(A, B, "PUBLIC_TRANSIT")]


def test_cache_key_includes_inner_route_option():
    walk_a = CachedRouteProvider(SimpleNamespace(walking_route_mode="ACCESSIBLE", route=lambda *_: None))
    walk_b = CachedRouteProvider(SimpleNamespace(walking_route_mode="SHORTEST", route=lambda *_: None))

    assert walk_a._options() != walk_b._options()


def test_cached_none_is_not_requested_again():
    inner = CountingRoutes(default=None)
    provider = CachedRouteProvider(inner)

    assert provider.route(*leg(A, B)) is None
    assert provider.route(*leg(A, B)) is None
    assert len(inner.calls) == 1


def test_budget_exceeded_returns_unknown_without_calling_provider():
    inner = CountingRoutes()
    provider = CachedRouteProvider(inner, max_calls=2, max_candidate_calls=2)

    provider.route(*leg(A, B))
    provider.route(*leg(B, C))

    assert provider.route(*leg(A, C)) is None
    assert len(inner.calls) == 2
    # Cached legs stay available after the budget is spent.
    assert provider.route(*leg(A, B)) == RouteEstimate(600, "CAR")


def test_candidate_phase_cannot_spend_itinerary_validation_budget():
    inner = CountingRoutes()
    provider = CachedRouteProvider(inner, max_calls=4, max_candidate_calls=1)

    with provider.candidate_phase():
        assert provider.route(*leg(A, B)) is not None
        assert provider.route(*leg(A, C)) is None  # candidate share used up

    # The denied leg was not cached as UNKNOWN; validation can still fetch it.
    assert provider.route(*leg(A, C)) == RouteEstimate(600, "CAR")
    assert provider.route(*leg(B, C)) == RouteEstimate(600, "CAR")
    assert len(inner.calls) == 3


def test_candidate_filter_uses_candidate_share(service):
    generator, session, _, _ = service
    session.places.extend([Place(105, "Second", latitude=37.6, longitude=126.8), Place(106, "Third", latitude=37.7, longitude=126.7)])
    inner = CountingRoutes(default=None)
    generator.route_provider = CachedRouteProvider(inner, max_calls=10, max_candidate_calls=1)

    retained = generator._mobility_candidates(session.places, [session.places[0]], session.trips[1], {})

    assert [place.place_id for place in retained] == [101, 104, 105, 106]
    assert len(inner.calls) == 1
    assert generator.route_provider.candidate_calls == 1


def test_each_request_dependency_gets_a_new_cache(monkeypatch):
    settings = Settings(route_provider="kakao", kakao_rest_api_key="test-key")
    inner = CountingRoutes()
    monkeypatch.setattr(factory, "get_settings", lambda: settings)
    monkeypatch.setattr(factory, "get_route_provider", lambda _settings=None: inner)

    first = factory.provide_route_provider()
    second = factory.provide_route_provider()
    first.route(*leg(A, B))
    second.route(*leg(A, B))

    assert isinstance(first, CachedRouteProvider) and first is not second
    assert (first.max_calls, first.max_candidate_calls) == (40, 16)
    assert len(inner.calls) == 2


def test_unavailable_provider_is_returned_unchanged(monkeypatch):
    monkeypatch.setattr(factory, "get_settings", lambda: Settings())

    provider = factory.provide_route_provider()

    assert isinstance(provider, UnavailableRouteProvider)
    assert provider.route(*leg(A, B)) is None


def test_modes_without_external_request_do_not_use_budget():
    inner = CountingRoutes(default=None)
    provider = CachedRouteProvider(inner, max_calls=1, max_candidate_calls=1)

    for mode in ("MIXED", "OTHER", None):
        assert provider.route(*leg(A, B, mode)) is None
    assert provider.calls == 0
    assert provider.route(*leg(A, B, "CAR")) is None  # real-call budget still available
    assert provider.calls == 1
