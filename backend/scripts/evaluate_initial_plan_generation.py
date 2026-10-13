"""Initial itinerary generation quality run against a disposable MySQL only.

Launched by scripts/run_initial_plan_eval_isolated_mysql.ps1, which creates
and verifies a fresh MySQL instance first.  This script re-verifies that
target, seeds one saved trip (Jeju 67 or Busan 68) from the read-only export,
runs the real PlanGenerationService once, and writes JSON + Markdown results.

    --provider mock   real EXAONE provider code with a fake, offline Ollama client
    --provider real   the configured Ollama EXAONE provider (user-run only)

Kakao place search is never used (place_provider=None): candidates are only
the exported places, so the run is repeatable.  No credential is printed.
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import monotonic
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.models.place import Place  # noqa: E402
from app.models.trip import Trip, TripInterest, TripPreference  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.external.ai.provider import GeneratedPlanDraft, PlanDraftDay, PlanDraftItem  # noqa: E402
from app.services.external.routing import CachedRouteProvider, RouteEstimate, UnavailableRouteProvider  # noqa: E402
from app.services.place_temporal_validation import opening_hours_match, verified_hours  # noqa: E402
from app.services.plan_generation_service import ACTIVITY_CANDIDATES_PER_DAY, INTEREST_CATEGORY_TOKENS, PlanGenerationService, REST_CAFE_UNDECIDED  # noqa: E402
from app.services.plan_quality_rules import candidate_supply, distance_meters, is_cafe, is_food_or_cafe, is_restaurant  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_plan_quality import evaluate as review_export  # noqa: E402

TRIPS = {"jeju": "67", "busan": "68", "trip76": "76"}
TRIP_LABELS = {"jeju": "제주", "busan": "부산", "trip76": "부산 (trip 76 기준)"}
# Manual scores and stored warning counts from docs/exaone_itinerary_quality_performance_review.md
# and the Windows run reported by the user (pre-Phase 2 baseline).
MANUAL_BASELINE = {"67": {"score": 47, "warnings": 11}, "68": {"score": 54, "warnings": 5}}
ISOLATED_PORTS = range(34000, 35000)
INSTANCE_PARENT = PROJECT_ROOT / ".initial_plan_eval_mysql"
MEAL_CODES = {"MEAL_OUTSIDE_WINDOW", "DUPLICATE_MEAL", "TOO_MANY_MEALS", "BACK_TO_BACK_MEALS", "LONG_MEAL_TRAVEL"}
STAY_CODES = {"LONG_MEAL", "LONG_STAY", "SHORT_STAY"}


class UnsafeTarget(RuntimeError):
    pass


def verify_evaluation_configuration(args):
    """Fail closed before a real provider can be constructed or called.

    This is intentionally evaluation-only: it verifies the current source and
    configured request budgets without changing application settings.
    """
    from app.services.external.ai.exaone_plan_provider import (
        MAX_SCHEMA_RETRY_MODEL_CALLS,
        PLAN_SYSTEM_PROMPT,
    )
    from app.services.external.routing.cached_provider import (
        DEFAULT_MAX_CALLS_PER_REQUEST,
        DEFAULT_MAX_CANDIDATE_CALLS_PER_REQUEST,
    )

    settings = get_settings()
    required_prompt_rules = (
        "FREE_TIME is only an unscheduled, location-unknown flexible interval",
        "Do not label FREE_TIME as a nearby walk",
        "no more than two non-food PLACE visits",
    )
    if any(rule not in PLAN_SYSTEM_PROMPT for rule in required_prompt_rules):
        raise UnsafeTarget("current EXAONE quality prompt is not loaded from the expected source")
    if MAX_SCHEMA_RETRY_MODEL_CALLS != 2:
        raise UnsafeTarget("EXAONE retry cap is not two calls")
    if (settings.route_max_calls_per_request, settings.route_max_candidate_calls_per_request) != (
        DEFAULT_MAX_CALLS_PER_REQUEST,
        DEFAULT_MAX_CANDIDATE_CALLS_PER_REQUEST,
    ):
        raise UnsafeTarget("route call budgets differ from 40 total / 16 candidate")
    if args.provider == "real" and settings.plan_provider == "mock":
        raise UnsafeTarget("PLAN_PROVIDER=real is required for --provider real")
    if args.provider == "real" and (not settings.exaone_base_url.strip() or not settings.exaone_model.strip()):
        raise UnsafeTarget("EXAONE base URL and model are required for --provider real")
    if args.candidates == "kakao" and settings.place_provider == "mock":
        raise UnsafeTarget("PLACE_PROVIDER=real is required for --candidates kakao")
    if (args.candidates == "kakao" or args.route_provider == "kakao") and not settings.kakao_rest_api_key.get_secret_value():
        raise UnsafeTarget("Kakao REST API key is required for the selected real provider")
    if args.route_provider == "kakao" and settings.route_provider != "kakao":
        raise UnsafeTarget("ROUTE_PROVIDER=kakao is required for --route-provider kakao")
    return {
        "prompt_rules_loaded": True,
        "ollama_max_calls": MAX_SCHEMA_RETRY_MODEL_CALLS,
        "route_max_calls": settings.route_max_calls_per_request,
        "route_max_candidate_calls": settings.route_max_candidate_calls_per_request,
        "plan_provider": settings.plan_provider,
        "route_provider": settings.route_provider,
    }


def _norm(path):
    return os.path.normcase(os.path.abspath(str(path))).rstrip("\\/")


def verify_isolated_target():
    """Abort unless every DB path points at the launcher's disposable instance."""
    raw_url = os.environ.get("INITIAL_PLAN_EVAL_MYSQL_URL")
    expected_datadir = os.environ.get("INITIAL_PLAN_EVAL_MYSQL_DATADIR")
    if not raw_url or not expected_datadir:
        raise UnsafeTarget("launcher variables are missing; run the .ps1 launcher")
    url = make_url(raw_url)
    if url.host != "127.0.0.1" or url.port not in ISOLATED_PORTS:
        raise UnsafeTarget("URL is not a 127.0.0.1 port in 34000-34999")
    if not (url.database or "").startswith("initial_plan_eval_"):
        raise UnsafeTarget("database name is not an evaluation database")
    if not _norm(expected_datadir).startswith(_norm(INSTANCE_PARENT) + os.sep):
        raise UnsafeTarget("datadir is outside .initial_plan_eval_mysql")
    settings = get_settings()
    # Anything inside the service that opens get_engine() must hit the same instance.
    if (settings.mysql_host, settings.mysql_port, settings.mysql_database) != (url.host, url.port, url.database):
        raise UnsafeTarget("application MYSQL_* settings differ from the isolated target")
    engine = create_engine(raw_url, pool_pre_ping=True)
    with engine.connect() as connection:
        port, datadir, database = connection.execute(text("SELECT @@port, @@datadir, DATABASE()")).one()
    if int(port) != url.port or _norm(datadir) != _norm(expected_datadir) or database != url.database:
        engine.dispose()
        raise UnsafeTarget("live server facts do not match the isolated instance")
    return engine, {"host": url.host, "port": int(port), "datadir": _norm(datadir), "database": database}


def _json_value(value):
    if isinstance(value, str) and value[:1] in "{[":
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _row(model, data, drop=("created_at", "updated_at")):
    columns = {column.key for column in model.__table__.columns}
    return {key: value for key, value in data.items() if key in columns and key not in drop}


def seed(session, exported):
    user = User(nickname="initial-plan-eval", status="ACTIVE", profile_completed=True)
    session.add(user)
    session.flush()
    trip_row = exported["trip"]
    trip = Trip(**_row(Trip, trip_row), user_id=user.user_id)
    trip.start_date = date.fromisoformat(str(trip_row["start_date"]))
    trip.end_date = date.fromisoformat(str(trip_row["end_date"]))
    session.add(trip)
    for row in exported.get("trip_preferences") or []:
        session.add(TripPreference(**_row(TripPreference, row, ("trip_preference_id", "created_at", "updated_at"))))
    for row in exported.get("trip_interests") or []:
        session.add(TripInterest(**_row(TripInterest, row, ("trip_interest_id", "created_at", "confirmed_at"))))
    for row in exported.get("places") or []:
        data = _row(Place, row)
        data["opening_hours"] = _json_value(data.get("opening_hours"))
        if data.get("details_updated_at"):
            data["details_updated_at"] = datetime.fromisoformat(str(data["details_updated_at"]))
        session.add(Place(**data))
    session.commit()
    return user.user_id, trip.trip_id


class EvalMockProvider:
    """Deterministic multi-day draft from the supplied candidates (no network)."""

    def generate_plan(self, trip, preferences, companions, interests, preference_context, places):
        def kind(place):
            category = place.get("category") or ""
            if "카페" in category or "CE7" in category:
                return "cafe"
            return "food" if place.get("activity_kind") == "FOOD_OR_CAFE" else "sight"
        pools = {name: [p for p in places if kind(p) == name] for name in ("sight", "cafe", "food")}
        slots = (("10:00", "11:30", ("sight", "cafe")), ("12:00", "13:00", ("food",)),
                 ("14:30", "16:00", ("sight", "cafe")), ("16:30", "17:00", ()),
                 ("18:00", "19:00", ("food",)))
        days, current = [], trip["start_date"]
        while current <= trip["end_date"]:
            items = []
            for sequence, (start, end, wanted) in enumerate(slots, start=1):
                place = next((pools[name].pop(0) for name in wanted if pools[name]), None)
                item_type = "REST" if not wanted else ("FREE_TIME" if place is None else ("MEAL" if wanted == ("food",) else "PLACE"))
                items.append(PlanDraftItem(sequence, item_type, place["name"] if place else "휴식",
                                           place["place_id"] if place else None, start, end, "mock"))
            days.append(PlanDraftDay(visit_date=current, items=items))
            current += timedelta(days=1)
        return GeneratedPlanDraft(days=days)


def instrument(provider, calls):
    """Time every Ollama call and keep its token counts (no prompt or answer text)."""
    original_chat = provider.client.chat

    def timed_chat(**kwargs):
        started, record = monotonic(), {"call": len(calls) + 1}
        calls.append(record)
        try:
            response = original_chat(**kwargs)
        except AppError as exc:
            record["error"] = exc.code
            raise
        finally:
            record["elapsed_ms"] = round((monotonic() - started) * 1000)
        stats = response if isinstance(response, dict) else {}
        ms = lambda key: round(stats[key] / 1_000_000) if isinstance(stats.get(key), (int, float)) else None  # noqa: E731
        record.update(load_ms=ms("load_duration"), prompt_tokens=stats.get("prompt_eval_count"),
                      prompt_ms=ms("prompt_eval_duration"), output_tokens=stats.get("eval_count"),
                      output_ms=ms("eval_duration"), total_ms=ms("total_duration"), done_reason=stats.get("done_reason"))
        return response

    provider.client.chat = timed_chat
    return provider


def capture_input(provider, captured):
    """Record what PlanGenerationService actually hands the model."""
    original = provider.generate_plan

    def generate_plan(trip, preferences, companions, interests, preference_context, places):
        captured.update(trip=trip, places=places)
        return original(trip, preferences, companions, interests, preference_context, places)

    provider.generate_plan = generate_plan
    return provider


def real_provider(calls):
    from app.services.external.factory import get_plan_generation_provider
    settings = get_settings()
    if settings.plan_provider == "mock":
        raise UnsafeTarget("PLAN_PROVIDER=real is required for --provider real")
    provider = instrument(get_plan_generation_provider(settings), calls)
    return provider, {"model": settings.exaone_model, "num_ctx": settings.exaone_num_ctx,
                      "ai_timeout_seconds": settings.ai_api_timeout_seconds}


class FakeOllamaClient:
    """No network. Call 1 repeats a place (backend rejects it), call 2 is valid,
    so the real EXAONE provider's retry and diagnostics path runs end to end."""

    STATS = {"load_duration": 1_000_000, "prompt_eval_count": 3000, "prompt_eval_duration": 5_000_000,
             "eval_count": 1000, "eval_duration": 50_000_000, "total_duration": 60_000_000, "done_reason": "stop"}

    def __init__(self, captured):
        self.captured = captured
        self.answers = 0

    def chat(self, *, model, messages, format_schema=None, options=None):
        self.answers += 1
        trip, places = self.captured["trip"], self.captured["places"]
        trip = {**trip, "start_date": date.fromisoformat(str(trip["start_date"])), "end_date": date.fromisoformat(str(trip["end_date"]))}
        draft = EvalMockProvider().generate_plan(trip, {}, [], [], {}, places)
        days = [{"visit_date": day.visit_date.isoformat(), "items": [
            {"sequence": i.sequence, "item_type": i.item_type, "title": i.title, "place_id": i.place_id,
             "start_time": i.start_time, "end_time": i.end_time} for i in day.items]} for day in draft.days]
        if self.answers == 1 and len(days) > 1:
            repeated = next(i for i in days[0]["items"] if i["place_id"] is not None)
            days[1]["items"][0] = {**days[1]["items"][0], "item_type": repeated["item_type"], "title": repeated["title"], "place_id": repeated["place_id"]}
        return {"message": {"content": json.dumps({"days": days}, ensure_ascii=False)}, **self.STATS}


class ReplayOllamaClient:
    """No network.  Answers with a saved real EXAONE itinerary (result.json of
    an earlier run), so post-processing changes can be compared on real output."""

    STATS = {"done_reason": "stop"}

    def __init__(self, items):
        days = {}
        for row in items:
            days.setdefault(str(row["visit_date"]), []).append({
                "sequence": row["sequence_no"], "item_type": row["item_type"], "title": row["title"],
                "place_id": row["place_id"], "start_time": str(row["start_time"])[:5], "end_time": str(row["end_time"])[:5]})
        self.content = json.dumps({"days": [{"visit_date": key, "items": value} for key, value in sorted(days.items())]}, ensure_ascii=False)

    def chat(self, *, model, messages, format_schema=None, options=None):
        return {"message": {"content": self.content}, **self.STATS}


def replay_exaone_provider(calls, items, source):
    from app.services.external.ai.exaone_plan_provider import ExaonePlanGenerationProvider
    provider = ExaonePlanGenerationProvider("http://replay.invalid", "replay", 180, client=ReplayOllamaClient(items))
    return instrument(provider, calls), {"model": f"replay of {source} (no network)", "num_ctx": provider.num_ctx, "ai_timeout_seconds": 180}


def route_risk(data):
    """Each leg between located stops: straight distance, scheduled gap, verified or not.

    The 0.25 km per gap-minute screen only marks legs to check; it is not a
    travel time and nothing is stored from it."""
    places = {row["place_id"]: SimpleNamespace(**row) for row in data["places"]}
    by_day = {}
    for row in data["plan_items"]:
        if row.get("place_id") in places and row.get("start_time"):
            by_day.setdefault(row["visit_date"], []).append(row)
    legs = []
    for day, rows in sorted(by_day.items()):
        rows.sort(key=lambda r: r["start_time"])
        for previous, current in zip(rows, rows[1:]):
            meters = distance_meters(places[previous["place_id"]], places[current["place_id"]])
            gap = (_clock(current["start_time"]).hour * 60 + _clock(current["start_time"]).minute) - (_clock(previous["end_time"]).hour * 60 + _clock(previous["end_time"]).minute)
            verified = current.get("travel_minutes_from_previous") is not None
            check = not verified and meters is not None and (meters > 5000 or meters / 1000 > gap * 0.25)
            legs.append({"visit_date": day, "from": places[previous["place_id"]].name, "to": places[current["place_id"]].name,
                         "straight_km": round(meters / 1000, 1) if meters is not None else None, "gap_min": gap,
                         "verified_minutes": current.get("travel_minutes_from_previous"),
                         "verified_distance_meters": current.get("travel_distance_meters_from_previous"),
                         "route_fact_status": "KNOWN" if verified else "UNKNOWN", "needs_check": check})
    return legs


def rest_coverage_credits(stops, days):
    """Credit a declared rest, but do not call an undecided cafe venue verified."""
    credits = []
    for day in days:
        day_stops = [(row, place) for row, place in stops if row["visit_date"] == day]
        if any(place is not None and is_cafe(place) for _, place in day_stops):
            credits.append(1.0)
        elif any(row["item_type"] == "REST" for row, _ in day_stops):
            undecided = any(
                row["item_type"] == "REST" and row.get("title") == REST_CAFE_UNDECIDED
                for row, _ in day_stops
            )
            credits.append(0.5 if undecided else 1.0)
        else:
            credits.append(0.0)
    return sum(credits)


class EvalMockRouteProvider:
    """Offline route facts for evaluation wiring tests; never derives coordinates."""

    SUPPORTED = {"CAR", "WALK", "PUBLIC_TRANSIT"}

    def route(self, origin_latitude, origin_longitude, destination_latitude, destination_longitude, transport_mode):
        if transport_mode not in self.SUPPORTED:
            return None
        seconds = {"CAR": 600, "WALK": 1200, "PUBLIC_TRANSIT": 900}[transport_mode]
        return RouteEstimate(seconds, transport_mode, distance_meters=1600,
                             walking_seconds=seconds if transport_mode == "WALK" else None)


class RouteMetricsProvider:
    """Count provider calls and durations without recording credentials or coordinates."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def route(self, origin_latitude, origin_longitude, destination_latitude, destination_longitude, transport_mode):
        started = monotonic()
        estimate = self.inner.route(origin_latitude, origin_longitude, destination_latitude, destination_longitude, transport_mode)
        self.calls.append({"mode": transport_mode, "elapsed_ms": round((monotonic() - started) * 1000),
                           "status": "KNOWN" if estimate is not None else "UNKNOWN"})
        return estimate


def route_provider_for(mode):
    """Return a request-scoped cached provider and report-safe metrics metadata."""
    settings = get_settings()
    if mode == "unavailable":
        return UnavailableRouteProvider(), {"mode": "unavailable", "source": "no route provider", "calls": []}
    if mode == "mock":
        metered = RouteMetricsProvider(EvalMockRouteProvider())
        source = "deterministic offline fixture; not an actual route"
    else:
        from app.services.external.factory import get_route_provider
        if settings.route_provider != "kakao":
            raise UnsafeTarget("ROUTE_PROVIDER=kakao is required for --route-provider kakao")
        metered = RouteMetricsProvider(get_route_provider(settings))
        source = "Kakao API; only selected by explicit --route-provider kakao"
    cached = CachedRouteProvider(metered, max_calls=settings.route_max_calls_per_request,
                                 max_candidate_calls=settings.route_max_candidate_calls_per_request)
    return cached, {"mode": mode, "source": source, "calls": metered.calls, "cache": cached}


def route_metrics(metadata, generated):
    """Keep API-call facts separate from DB-leg facts and straight-line screens."""
    calls = metadata.get("calls", [])
    legs = route_risk(generated)
    known = sum(row["route_fact_status"] == "KNOWN" for row in legs)
    unknown = sum(row["route_fact_status"] == "UNKNOWN" for row in legs)
    return {"provider": metadata["mode"], "source": metadata["source"], "provider_calls": len(calls),
            "provider_elapsed_ms": sum(row["elapsed_ms"] for row in calls),
            "provider_known": sum(row["status"] == "KNOWN" for row in calls),
            "provider_unknown": sum(row["status"] == "UNKNOWN" for row in calls),
            "provider_call_details": [dict(row) for row in calls],
            "cache_external_calls": getattr(metadata.get("cache"), "calls", 0),
            "cache_candidate_calls": getattr(metadata.get("cache"), "candidate_calls", 0),
            "stored_known_legs": known, "stored_unknown_legs": unknown}


def mock_exaone_provider(calls, captured):
    from app.services.external.ai.exaone_plan_provider import ExaonePlanGenerationProvider
    provider = ExaonePlanGenerationProvider("http://mock.invalid", "mock-exaone", 180, client=FakeOllamaClient(captured))
    return instrument(provider, calls), {"model": "mock-exaone (no network)", "num_ctx": provider.num_ctx, "ai_timeout_seconds": 180}


def candidate_diagnostics(places, trip_days, source, preferences=None):
    """Non-food (sight/experience) supply before generation. Counts only, never invented."""
    def is_food(place):
        if isinstance(place, dict):
            return place.get("activity_kind") == "FOOD_OR_CAFE"
        return is_food_or_cafe(place)

    def category(place):
        return (place.get("category") if isinstance(place, dict) else place.category) or ""

    def name(place):
        return place.get("name") if isinstance(place, dict) else place.name

    non_food = [p for p in places if not is_food(p)]
    cafes = [p for p in places if is_food(p) and ("카페" in category(p) or "CE7" in category(p))]
    wanted = trip_days * ACTIVITY_CANDIDATES_PER_DAY
    targets = PlanGenerationService._candidate_targets(trip_days, preferences)
    wanted = targets["sights"]
    supply = candidate_supply([SimpleNamespace(**p) if isinstance(p, dict) else p for p in places], trip_days, targets=targets)
    labels = {"SIGHTS_FEWER_THAN_DAYS": "비음식 후보가 일수보다 적음", "SIGHTS_BELOW_TWO_PER_DAY": f"비음식 후보가 목표({wanted}곳) 미만",
              "SINGLE_AREA": "비음식 후보가 한 권역(반경 2km)에 집중", "SIGHTS_WITHOUT_COORDINATES": "좌표 없는 비음식 후보 있음",
              "RESTAURANTS_FEWER_THAN_MEALS": f"식당이 점심·저녁 수({targets['restaurants']}곳)보다 적음"}
    status = " / ".join(labels[code] for code in supply["problems"]) or "충분"
    return {"source": source, "total": len(places), "non_food": len(non_food), "food": len(places) - len(non_food) - len(cafes),
            "cafe": len(cafes), "trip_days": trip_days, "recommended_non_food": wanted, "status": status,
            "non_food_places": [f"{name(p)} ({category(p) or '-'})" for p in non_food],
            "sight_types": supply["sight_types"], "areas": supply["areas"], "area_sizes": supply["area_sizes"],
            "restaurants": supply["restaurants"], "targets": targets, "shortfall": supply["shortfall"],
            "problems": supply["problems"]}


CANDIDATE_MODES = ("export", "fixture", "kakao")
FIXTURE_FILE = Path(__file__).resolve().parent / "fixtures" / "phase3b_synthetic_places.json"
FIXTURE_QUERY_KINDS = {"관광지": "sight", "문화시설": "sight", "공원": "sight", "박물관": "sight",
                       "맛집": "restaurant", "음식점": "restaurant", "카페": "cafe"}


class FixturePlaceProvider:
    """Mock-only place search over a SYNTHETIC fixture ([가상] names).

    It lets the service's own backfill path run without Kakao.  The places are
    not real, so a run with this provider is never a quality result.
    """

    def __init__(self, destination, path=FIXTURE_FILE):
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
        self.rows = rows.get(destination, [])
        self.searches = []

    @staticmethod
    def _kind(category):
        if "카페" in category:
            return "cafe"
        return "restaurant" if category.startswith("음식점") else "sight"

    def search(self, query, region=None):
        from app.services.external.place.provider import PlaceCandidate
        self.searches.append(query)
        kind = FIXTURE_QUERY_KINDS.get(query)
        return [PlaceCandidate("KAKAO", row["external_id"], row["name"], row["category"], row["address"],
                               row["latitude"], row["longitude"], None, None)
                for row in self.rows if kind is None or self._kind(row["category"]) == kind]

    def search_nearby(self, latitude, longitude, radius_meters, category_codes, limit_per_category):
        return []


def place_provider_for(mode, destination, provider_mode):
    """export: no search (saved places only).  fixture: synthetic, Mock only.
    kakao: the configured real place provider (user-run only)."""
    if mode == "export":
        return None, "과거 여행에 쓰인 장소만 (검색 보충 없음)"
    if mode == "fixture":
        if provider_mode == "real":
            raise UnsafeTarget("--candidates fixture is synthetic and only allowed with --provider mock")
        return FixturePlaceProvider(destination), "export 장소 + 합성 fixture 검색 보충 ([가상] 장소, Mock 전용)"
    from app.services.external.factory import get_place_provider
    settings = get_settings()
    if settings.place_provider == "mock":
        raise UnsafeTarget("PLACE_PROVIDER=real is required for --candidates kakao")
    return get_place_provider(settings), "export 장소 + 실제 Kakao 검색 보충"


def collect(session, trip_id):
    q = lambda sql, **p: [dict(r._mapping) for r in session.execute(text(sql), p)]  # noqa: E731
    trip = q("SELECT trip_id, destination, start_date, end_date, transport_mode FROM trips WHERE trip_id=:id", id=trip_id)[0]
    plans = q("SELECT plan_id FROM travel_plans WHERE trip_id=:id", id=trip_id)
    items, issues = [], []
    for plan in plans:
        items += q("SELECT * FROM plan_items WHERE plan_id=:id ORDER BY visit_date, sequence_no", id=plan["plan_id"])
        issues += q("SELECT issue_type, severity, message FROM plan_validation_issues WHERE plan_id=:id", id=plan["plan_id"])
    places = q("SELECT * FROM places")
    return {"trip": trip, "plan_items": items, "places": places, "validation_issues": issues}


def _clock(value):
    if value is None or isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        return (datetime.min + value).time()
    return time.fromisoformat(str(value).zfill(8))


def normalize_export(data):
    """Same shape as docs/task75q_trip_export.json for the shared quality rules."""
    for item in data["plan_items"]:
        item["visit_date"] = str(item["visit_date"])
        for key in ("start_time", "end_time"):
            item[key] = _clock(item[key]).strftime("%H:%M:%S") if item[key] is not None else None
    for place in data["places"]:
        place["opening_hours"] = _json_value(place.get("opening_hours"))
    data["trip"]["start_date"] = str(data["trip"]["start_date"])
    data["trip"]["end_date"] = str(data["trip"]["end_date"])
    return data


def critical_errors(data, candidate_ids, error):
    found = []
    if error:
        found.append(f"GENERATION_FAILED: {error}")
        return found
    start, end = date.fromisoformat(data["trip"]["start_date"]), date.fromisoformat(data["trip"]["end_date"])
    by_day = {}
    for item in data["plan_items"]:
        by_day.setdefault(item["visit_date"], []).append(item)
    expected = {str(start + timedelta(days=i)) for i in range((end - start).days + 1)}
    for missing in sorted(expected - set(by_day)):
        found.append(f"EMPTY_DAY: {missing}")
    for day in sorted(set(by_day) - expected):
        found.append(f"DATE_OUTSIDE_TRIP: {day}")
    seen = set()
    for day, rows in by_day.items():
        previous_end = None
        for row in sorted(rows, key=lambda r: r["sequence_no"]):
            s, e = _clock(row["start_time"]), _clock(row["end_time"])
            if s and e and e < s:
                found.append(f"END_BEFORE_START: {day} #{row['sequence_no']}")
            if s and previous_end and s < previous_end:
                found.append(f"TIME_OVERLAP: {day} #{row['sequence_no']}")
            previous_end = e or previous_end
            place_id = row.get("place_id")
            if place_id is not None:
                if place_id not in candidate_ids:
                    found.append(f"PLACE_NOT_IN_CANDIDATES: {place_id}")
                if place_id in seen:
                    found.append(f"DUPLICATE_PLACE: {place_id}")
                seen.add(place_id)
    return found


def auto_score(data, warnings, interests, travel_style):
    """Automated proxy of the 6.3 rubric.  Unverifiable parts never get full marks."""
    places = {row["place_id"]: SimpleNamespace(**row) for row in data["places"]}
    rows = data["plan_items"]
    stops = [(row, places.get(row.get("place_id"))) for row in rows]
    visits = [(row, place) for row, place in stops if place is not None]
    codes = [finding.code for finding in warnings]
    count = lambda wanted: sum(code in wanted or any(code.startswith(w) for w in wanted if w.endswith("_")) for code in codes)  # noqa: E731
    days = sorted({row["visit_date"] for row in rows}) or ["-"]
    n = max(1, len(visits))
    unverified = []

    grounded = sum(bool(p.kakao_place_id and p.address and p.latitude is not None) for _, p in visits) / n
    type_ok = sum(PlanGenerationService._canonical_item_type(p) == r["item_type"] for r, p in visits) / n
    non_food = sum(not is_food_or_cafe(p) for _, p in visits)
    fit = max(0.0, 10 * min(1.0, non_food / max(1, len(visits) * 0.5)) - 2 * count({"DUPLICATE_LOCATION"}) - 2 * count({"FOOD_ONLY_DAY"}))
    unverified.append("장소 실존·영업 여부: 검증 불가 → 실재 근거 10점 중 최대 8점")
    place_score = 8 * grounded + 5 * type_ok + fit

    spread_ok, centers = 0, []
    for day in days:
        coords = [p for r, p in visits if r["visit_date"] == day and p.latitude is not None]
        widest = max((distance_meters(a, b) or 0 for a in coords for b in coords), default=0)
        spread_ok += widest <= 15000
        if coords:
            centers.append(SimpleNamespace(latitude=sum(float(p.latitude) for p in coords) / len(coords),
                                           longitude=sum(float(p.longitude) for p in coords) / len(coords)))
    distinct_days = sum(all((distance_meters(c, o) or 0) > 3000 for o in centers if o is not c) for c in centers)
    legs = route_risk(data)
    measured = sum(leg["route_fact_status"] == "KNOWN" for leg in legs)
    leg_score = 9 * measured / len(legs) + 3 * (len(legs) - measured) / len(legs) if legs else 3
    if measured < len(legs):
        unverified.append(f"이동시간: {len(legs) - measured}/{len(legs)}구간 실측 없음(UNKNOWN은 9점 중 3점만 인정)")
    route_score = 8 * spread_ok / len(days) + (8 * distinct_days / len(centers) if len(centers) > 1 else 4) + leg_score

    meal = max(0, 8 - 2 * (count(MEAL_CODES) + count({"MISSING_"})))
    stay = max(0, 6 - 2 * count(STAY_CODES))
    hours = [opening_hours_match(p, date.fromisoformat(r["visit_date"]), _clock(r["start_time"]), _clock(r["end_time"])) for r, p in visits]
    hours_score = 6 * sum(h is True for h in hours) / n + 1 * sum(h is None for h in hours) / n
    if any(h is None for h in hours):
        unverified.append(f"영업시간: {sum(h is None for h in hours)}/{len(hours)}곳 검증 불가(6점 중 최대 1점)")
    if any(h is False for h in hours):
        unverified.append(f"영업시간 불일치 {sum(h is False for h in hours)}곳")
    time_score = meal + stay + hours_score

    text_of = lambda p: f"{p.category or ''} {p.name or ''}"  # noqa: E731
    covered = [code for code in interests
               if any(token in text_of(p) for _, p in visits for token in INTEREST_CATEGORY_TOKENS.get(code, (code,)))]
    kinds = {(p.category or "").split(">")[-1].strip() for _, p in visits}
    interest_score = 9 * len(covered) / max(1, len(interests)) + min(6, len(kinds))

    per_day_cap = 4 if travel_style == "SLOW" else 5
    per_day = [sum(r["visit_date"] == d for r, _ in visits) for d in days]
    # Too many stops, or a day left nearly empty (one visit or none), both miss the chosen pace.
    density = max(0, 5 - sum(max(0, c - per_day_cap) for c in per_day) - 1.5 * sum(c < 2 for c in per_day))
    rest_days = rest_coverage_credits(stops, days)
    burden = max(0, 5 - 1.5 * count({"UNVERIFIED_LONG_LEG"}))
    senior_score = density + 5 * rest_days / len(days) + burden

    areas = {
        "장소 정확성(25)": round(place_score, 1),
        "동선·이동시간(25)": round(route_score, 1),
        "시간표 현실성(20)": round(time_score, 1),
        "관심사·다양성(15)": round(interest_score, 1),
        "시니어·휴식(15)": round(senior_score, 1),
    }
    return {
        "areas": areas,
        "total": round(sum(areas.values()), 1),
        "unverified": unverified,
        "facts": {"visits": len(visits), "non_food_visits": non_food, "restaurants": sum(is_restaurant(p) for _, p in visits),
                  "interests_covered": covered, "days": len(days)},
    }


V2_CHANGES = [
    "이름·카테고리 일치는 서버가 강제하므로 5점→2점, 남는 3점은 같은 위치 중복이 없을 때만",
    "관광 적합성: 식당만 있는 날 -3, 같은 위치 -2",
    "일자 간 다양성: 방문 관광지의 권역 수(반경 2km) ÷ 일수, 반복 권역 -4",
    "이동시간 UNKNOWN은 9점 중 2점만 인정, 미검증 장거리 구간당 -1.5",
    "식사 규칙: 경고당 -2.5(점심·저녁 누락 포함), 과밀한 날은 체류 점수 -2",
    "관심사는 이름이 아니라 카테고리로만 인정, 유형 다양성은 비음식 관광 유형 수 × 2 (최대 6)",
    "시니어: 휴식은 REST와 카페만 인정, 연속 관광 -2, 날짜 간 불균형 -2",
]


def auto_score_v2(data, warnings, interests, travel_style):
    """Phase 3A rubric: same five areas, but no credit the server guarantees anyway."""
    places = {row["place_id"]: SimpleNamespace(**row) for row in data["places"]}
    rows = data["plan_items"]
    stops = [(row, places.get(row.get("place_id"))) for row in rows]
    visits = [(row, place) for row, place in stops if place is not None]
    sights = [(row, place) for row, place in visits if not is_food_or_cafe(place)]
    codes = [finding.code for finding in warnings]
    count = lambda *wanted: sum(code in wanted or any(code.startswith(w) for w in wanted if w.endswith("_")) for code in codes)  # noqa: E731
    days = sorted({row["visit_date"] for row in rows}) or ["-"]
    n = max(1, len(visits))
    unverified = []

    grounded = sum(bool(p.kakao_place_id and p.address and p.latitude is not None) for _, p in visits) / n
    unverified.append("장소 실존·영업 여부: 검증 불가 → 실재 근거 10점 중 최대 8점")
    place_score = (8 * grounded + 2 + (3 if not count("DUPLICATE_LOCATION") else 0)
                   + max(0.0, 10 * min(1.0, len(sights) / max(1, len(visits) * 0.5)) - 3 * count("FOOD_ONLY_DAY") - 2 * count("DUPLICATE_LOCATION")))

    spread_ok = 0
    for day in days:
        coords = [p for r, p in visits if r["visit_date"] == day and p.latitude is not None]
        spread_ok += max((distance_meters(a, b) or 0 for a in coords for b in coords), default=0) <= 15000
    areas = candidate_supply([p for _, p in sights], len(days))["areas"]
    variety = max(0.0, 8 * min(1.0, areas / len(days)) - 4 * count("REPEATED_AREA"))
    legs = route_risk(data)
    measured = sum(leg["route_fact_status"] == "KNOWN" for leg in legs)
    leg_score = max(0.0, (9 * measured + 2 * (len(legs) - measured)) / len(legs) - 1.5 * count("UNVERIFIED_LONG_LEG")) if legs else 2
    if measured < len(legs):
        unverified.append(f"이동시간: {len(legs) - measured}/{len(legs)}구간 실측 없음(UNKNOWN은 9점 중 2점)")
    route_score = 8 * spread_ok / len(days) + variety + leg_score

    meal = max(0.0, 8 - 2.5 * count("MEAL_OUTSIDE_WINDOW", "DUPLICATE_MEAL", "TOO_MANY_MEALS", "BACK_TO_BACK_MEALS", "LONG_MEAL_TRAVEL", "MISSING_"))
    stay = max(0, 6 - 2 * count("LONG_MEAL", "LONG_STAY", "SHORT_STAY", "CROWDED_DAY"))
    hours = [opening_hours_match(p, date.fromisoformat(r["visit_date"]), _clock(r["start_time"]), _clock(r["end_time"])) for r, p in visits]
    hours_score = 6 * sum(h is True for h in hours) / n + 1 * sum(h is None for h in hours) / n
    if any(h is None for h in hours):
        unverified.append(f"영업시간: {sum(h is None for h in hours)}/{len(hours)}곳 검증 불가(6점 중 최대 1점)")
    time_score = meal + stay + hours_score

    covered = [code for code in interests
               if any(token in (p.category or "") for _, p in visits for token in INTEREST_CATEGORY_TOKENS.get(code, (code,)))]
    sight_types = {(p.category or "").split(">")[-1].strip() for _, p in sights} - {""}
    interest_score = 9 * len(covered) / max(1, len(interests)) + min(6, 2 * len(sight_types))

    per_day_cap = 4 if travel_style == "SLOW" else 5
    per_day = [sum(r["visit_date"] == d for r, _ in visits) for d in days]
    density = max(0, 5 - sum(max(0, c - per_day_cap) for c in per_day) - 1.5 * sum(c < 2 for c in per_day)
                  - 2 * count("CONSECUTIVE_SIGHTS") - 2 * count("UNEVEN_DAYS"))
    rest_days = rest_coverage_credits(stops, days)
    burden = max(0, 5 - 1.5 * count("UNVERIFIED_LONG_LEG") - 1 * count("CONSECUTIVE_SIGHTS"))
    senior_score = density + 5 * rest_days / len(days) + burden

    areas_scores = {
        "장소 정확성(25)": round(place_score, 1),
        "동선·이동시간(25)": round(route_score, 1),
        "시간표 현실성(20)": round(time_score, 1),
        "관심사·다양성(15)": round(interest_score, 1),
        "시니어·휴식(15)": round(senior_score, 1),
    }
    return {"version": "v2", "areas": areas_scores, "total": round(sum(areas_scores.values()), 1), "unverified": unverified,
            "facts": {"visits": len(visits), "non_food_visits": len(sights), "sight_areas": areas,
                      "sight_types": sorted(sight_types), "interests_covered": covered, "days": len(days)}}


def review(data, interests, travel_style):
    warnings = review_export(data) if data["plan_items"] else []
    return warnings, auto_score(data, warnings, interests, travel_style), auto_score_v2(data, warnings, interests, travel_style)


def markdown(result):
    lines = [f"# 초기 일정 생성 평가: {result['trip_label']} (trip {result['source_trip_id']})", "",
             f"- 실행 시각: {result['run_at']}", f"- 모드: **{result['provider']}**" + (" (모델 출력이 아닌 결정적 Mock 초안, 점수는 저장 경로 검증용)" if result["provider"] == "mock" else ""),
             f"- 후보 모드: **{result['candidate_mode']}** ({result['candidate_source']})",
             f"- 후보 공급: **{'충분' if result['supply_ok'] else '부족 → 80점 판정 안 함'}**",
             f"- 결과: {'성공' if not result['error'] else '실패 ' + result['error']}",
             f"- 총 생성시간: {result['timing']['total_generation_ms']} ms",
             f"- 자동 잠정 점수 v2(Phase 3A): **{result['score_v2']['total']} / 100** · 80점 이상: **{'예' if result['passes_80'] else '아니요'}** · Critical: **{len(result['critical_errors'])}건**",
             f"- 참고: 기존 v1 점수 {result['score']['total']} (80점 이상 {'예' if result['passes_80_v1'] else '아니요'})",
             f"- 품질 경고: {len(result['quality_warnings'])}건", ""]
    lines += ["## Ollama 호출", "", "| 호출 | 결과 | 검증 실패 사유 | 재시도 | 경과 ms | 로드 ms | 입력 토큰 | 입력 ms | 출력 토큰 | 출력 ms | done | 오류 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in result["ollama_calls"] or [{}]:
        lines.append("| " + " | ".join(str(c.get(k) if c.get(k) is not None else "-") for k in ("call", "result", "validation_reason", "will_retry", "elapsed_ms", "load_ms", "prompt_tokens", "prompt_ms", "output_tokens", "output_ms", "done_reason", "error_code")) + " |")
    diagnostics = result["candidate_diagnostics"]
    lines += ["", "## 비음식 후보 진단(생성 전)", "", "| 기준 | 전체 | 관광·체험 등 비음식 | 식당 | 카페 | 목표(관광/식당/권역) | 관광 유형 수 | 권역 수(2km) | 부족분 | 판정 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in (diagnostics["seeded"], diagnostics["model_input"]):
        if d is not None:
            t, short = d["targets"], d["shortfall"]
            gap = ", ".join(f"{k} {v}" for k, v in short.items() if v) or "없음"
            lines.append(f"| {d['source']} | {d['total']} | {d['non_food']} | {d['restaurants']} | {d['cafe']} | {t['sights']}/{t['restaurants']}/{t['areas']} | {len(d['sight_types'])} | {d['areas']} | {gap} | {d['status']} |")
    if diagnostics["model_input"] is None:
        lines.append("| candidates sent to the model | 모델 호출 전에 실패해 확인 불가 | | | | | | | | |")
    lines += ["", "비음식 후보: " + (", ".join(diagnostics["seeded"]["non_food_places"]) or "없음"),
              "", "후보가 부족해도 임의 장소를 만들지 않습니다. 부족분은 그대로 보고합니다."]
    names = {p["place_id"]: p.get("name") for p in result["generated"]["places"]}
    opt = result.get("route_optimization") or {}
    metric = opt.get("metric")
    if metric == "ROUTE_SECONDS":
        decision_metric = (
            f"verified route duration: {opt.get('route_seconds_before')}s -> "
            f"{opt.get('route_seconds_after')}s"
        )
    elif metric == "STRAIGHT_LINE":
        decision_metric = "straight-line distance (no verified route metric available)"
    else:
        decision_metric = "not recorded"
    lines += ["", "## 동선 보정 (Phase 3C, 직선거리 기준)", "",
              f"- 적용: {'예' if opt.get('applied') else '아니요'}" + (f" (취소: {opt['reverted']})" if opt.get("reverted") else ""),
              f"- 하루 경로 합계(직선): {round((opt.get('before_m') or 0) / 1000, 1)}km → {round((opt.get('after_m') or 0) / 1000, 1)}km, "
              f"가장 긴 구간: {round((opt.get('longest_leg_before_m') or 0) / 1000, 1)}km → {round((opt.get('longest_leg_after_m') or 0) / 1000, 1)}km",
              "- 직선거리는 순서 판단에만 썼고 이동시간으로 바꾸지 않았습니다."]
    lines.append(f"- decision metric: {decision_metric}")
    if metric == "ROUTE_SECONDS":
        lines.append("- Order changes above were decided from verified RouteProvider durations; straight-line km remains diagnostic only.")
    for move in opt.get("moves", []):
        if isinstance(move.get("gain_seconds"), (int, float)):
            gain = f"verified route duration -{move['gain_seconds']}s"
        elif isinstance(move.get("gain_m"), (int, float)):
            gain = f"straight-line distance -{move['gain_m']}m"
        else:
            gain = "metric gain not recorded"
        lines.append(f"  - {move['visit_date']} #{move['sequence']} {move['kind']}: {names.get(move['from_place_id'])} → {names.get(move['to_place_id'])} ({gain})")
    for meal in opt.get("far_meals", []):
        lines.append(f"  - 주변에 적합한 식당 없음: {meal['visit_date']} #{meal['sequence']} {names.get(meal['place_id'])} (가장 가까운 일정까지 {meal['nearest_stop_m']}m)")
    for rest in opt.get("rest_breaks", []):
        lines.append(f"  - 휴식 배치: {rest['visit_date']} {rest['start']}–{rest['end']} ({names.get(rest['after_place_id'])} 방문 시간 일부, 휴식 시설 미확인)")
    if opt.get("rest_reverted"):
        lines.append(f"  - 휴식 배치 취소: {opt['rest_reverted']}")
    lines += ["", "## 이동 위험 구간 (실측 없음, 확인용)", "", "| 날짜 | 구간 | 직선 km | 간격(분) | 실측 이동(분) | 확인 필요 |", "|---|---|---|---|---|---|"]
    metrics = result.get("route_metrics")
    lines += ["", "## Route API metrics", ""]
    if metrics is None:
        # Saved reports created before route metrics were added remain useful;
        # no missing value is converted into a route fact.
        lines.append("- route metrics were not recorded by this older evaluation result")
    else:
        lines += [
            f"- provider: {metrics['provider']} ({metrics['source']})",
            f"- provider calls: {metrics['provider_calls']}; elapsed: {metrics['provider_elapsed_ms']} ms; provider facts KNOWN {metrics['provider_known']} / UNKNOWN {metrics['provider_unknown']}",
            f"- stored itinerary legs: KNOWN {metrics['stored_known_legs']} / UNKNOWN {metrics['stored_unknown_legs']}; cached external calls: {metrics['cache_external_calls']}",
            "- Straight-line km is only the Phase 3C optimizer/risk screen. API distance/time is separately labelled below and is never estimated.",
        ]
    for leg in result.get("route_risk", []):
        status = leg.get("route_fact_status") or ("KNOWN" if leg.get("verified_minutes") is not None else "UNKNOWN")
        distance = leg.get("verified_distance_meters")
        minutes = leg.get("verified_minutes")
        lines.append(f"- API leg fact: {leg['from']} -> {leg['to']}; status={status}; api_distance_m={distance if distance is not None else 'UNKNOWN'}; api_minutes={minutes if minutes is not None else 'UNKNOWN'}; straight_screen_km={leg['straight_km']}")
    for leg in result.get("route_risk", []):
        lines.append(f"| {leg['visit_date']} | {leg['from']} → {leg['to']} | {leg['straight_km']} | {leg['gap_min']} | {leg['verified_minutes'] if leg['verified_minutes'] is not None else 'UNKNOWN'} | {'예' if leg['needs_check'] else '-'} |")
    lines += ["", "## 생성된 일정", "", "| 날짜 | # | 시간 | 유형 | 장소 | 카테고리 | 이동(분) | 검증 |", "|---|---|---|---|---|---|---|---|"]
    names = {p["place_id"]: p for p in result["generated"]["places"]}
    located_days = set()
    for item in result["generated"]["plan_items"]:
        place = names.get(item.get("place_id")) or {}
        day_key = item["visit_date"]
        first_located_stop = item.get("place_id") is not None and day_key not in located_days
        if item.get("place_id") is not None:
            located_days.add(day_key)
        travel_display = (
            "NONE" if item.get("place_id") is None or first_located_stop
            else item.get("travel_minutes_from_previous")
        )
        lines.append(f"| {item['visit_date']} | {item['sequence_no']} | {(item['start_time'] or '')[:5]}–{(item['end_time'] or '')[:5]} | {item['item_type']} | "
                     f"{place.get('name') or item['title']} ({item.get('place_id')}) | {place.get('category') or '-'} | "
                     f"{travel_display if travel_display is not None else 'UNKNOWN'} | {item.get('validation_status')} |")
    lines += ["", "## 점수(자동 잠정)", "", "| 영역 | v1(기존) | v2(Phase 3A) |", "|---|---|---|"]
    lines += [f"| {k} | {v} | {result['score_v2']['areas'][k]} |" for k, v in result["score"]["areas"].items()]
    lines += [f"| 합계 | {result['score']['total']} | {result['score_v2']['total']} |", "", "v2에서 바뀐 기준:"] + [f"- {c}" for c in result["score_v2_changes"]]
    lines += ["", "검증 불가로 감점·보류한 항목:"] + [f"- {u}" for u in result["score"]["unverified"]]
    lines += ["", "## Critical 오류", ""] + ([f"- {c}" for c in result["critical_errors"]] or ["- 없음"])
    lines += ["", "## 품질 경고", ""] + ([f"- [{w['code']}] {w['message']}" for w in result["quality_warnings"]] or ["- 없음"])
    b = result["baseline"]
    lines += ["", "## 기존 일정과 비교", "", "| 항목 | 기존(Phase 2 전) | 이번 |", "|---|---|---|",
              f"| 수동 점수(리뷰 문서) | {b['manual_score']} (잠정) | - |",
              f"| 자동 점수 v1(기존 기준) | {b['score']['total']} | {result['score']['total']} |",
              f"| 자동 점수 v2(새 기준, 과거 일정도 재계산) | {b['score_v2']['total']} | {result['score_v2']['total']} |",
              f"| 품질 경고(Phase 3A 규칙으로 재계산) | {len(b['quality_warnings'])} (Phase 3A 이전 규칙 {b['manual_warnings']}) | {len(result['quality_warnings'])} |",
              f"| 방문 장소 수 / 비식당 | {b['score']['facts']['visits']} / {b['score']['facts']['non_food_visits']} | {result['score']['facts']['visits']} / {result['score']['facts']['non_food_visits']} |"]
    lines += ["", "## 비교 한계", ""] + [f"- {x}" for x in result["limitations"]]
    if metric == "ROUTE_SECONDS":
        for index, line in enumerate(lines):
            if line.startswith("## ") and "Phase 3C" in line:
                lines[index] = "## Route optimisation (verified RouteProvider duration)"
                break
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--trip", choices=sorted(TRIPS), required=True)
    parser.add_argument("--provider", choices=("mock", "real", "replay"), default="mock")
    parser.add_argument("--replay", help="result.json of an earlier real run (with --provider replay)")
    parser.add_argument("--candidates", choices=CANDIDATE_MODES, default="export")
    parser.add_argument("--route-provider", choices=("unavailable", "mock", "kakao"), default="unavailable")
    parser.add_argument("--export", default=str(PROJECT_ROOT / "docs" / "task75q_trip_export.json"))
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "docs" / "initial_plan_eval"))
    parser.add_argument("--preflight-only", action="store_true", help="verify the isolated target and provider caps without seeding or calling providers")
    args = parser.parse_args(argv)

    # Provider diagnostics (codes only, no prompt or answer text) also go to the console.
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(lambda record: record.getMessage().startswith(("exaone_model_", "EXAONE ", "plan_candidate_", "plan_route_", "plan_draft_repaired")))
    logging.getLogger("uvicorn.error").addHandler(handler)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    engine, target = verify_isolated_target()
    print(f"isolated target verified: 127.0.0.1:{target['port']} database={target['database']}")
    try:
        preflight = verify_evaluation_configuration(args)
        if args.preflight_only:
            print("preflight verified: " + json.dumps(preflight, ensure_ascii=True, sort_keys=True))
            return 0
    finally:
        if args.preflight_only:
            engine.dispose()
    source_id = TRIPS[args.trip]
    exported = json.loads(Path(args.export).read_text(encoding="utf-8"))["trips"][source_id]
    baseline_source = json.loads(json.dumps({k: exported[k] for k in ("trip", "plan_items", "places")}, default=str))
    interests = [row["interest_code"] for row in exported["trip_interests"]]
    travel_style = (exported["trip_preferences"] or [{}])[0].get("travel_style")
    calls, captured = [], {}
    replay = None
    if args.provider == "replay":
        if not args.replay:
            raise UnsafeTarget("--replay result.json is required with --provider replay")
        replay = json.loads(Path(args.replay).read_text(encoding="utf-8"))
        # The disposable DB gets the places of that run (incl. its Kakao results), so the
        # saved itinerary's place_ids exist; the "before" is that real itinerary.
        exported = {**exported, "places": replay["generated"]["places"]}
        baseline_source = json.loads(json.dumps({"trip": exported["trip"], "plan_items": replay["generated"]["plan_items"],
                                                 "places": replay["generated"]["places"]}, default=str))
        provider, meta = replay_exaone_provider(calls, replay["generated"]["plan_items"], Path(args.replay).parent.name)
    elif args.provider == "real":
        provider, meta = real_provider(calls)
    else:
        provider, meta = mock_exaone_provider(calls, captured)
    capture_input(provider, captured)
    trip_days = (date.fromisoformat(str(exported["trip"]["end_date"])) - date.fromisoformat(str(exported["trip"]["start_date"]))).days + 1
    preferences = {key: (exported["trip_preferences"] or [{}])[0].get(key) for key in ("travel_style", "rest_frequency", "walking_tolerance")}
    destination = exported["trip"]["destination"]
    place_provider, candidate_source = place_provider_for(args.candidates, destination, args.provider)
    seeded = candidate_diagnostics([SimpleNamespace(**row) for row in exported["places"]], trip_days, "seeded export places", preferences)
    print(f"candidates before generation: non_food={seeded['non_food']}/{seeded['total']} days={trip_days} status={seeded['status']}")

    route_provider, route_metadata = route_provider_for(args.route_provider)
    error, response_warnings, service = None, [], None
    with Session(engine) as session:
        user_id, trip_id = seed(session, exported)
        started = monotonic()
        try:
            service = PlanGenerationService(session, provider, place_provider=place_provider, route_provider=route_provider)
            response = service.generate(user_id, trip_id, [])
            response_warnings = list(response.warnings)
        except AppError as exc:
            error = f"{exc.code} ({exc.status_code}): {exc.message}"
            if getattr(exc, "validation_reason", None):
                error += f" [validation_reason={exc.validation_reason}]"
        except Exception as exc:  # recorded, not hidden: the run still writes its result files
            session.rollback()
            error = f"{type(exc).__name__}: {exc}"
        total_ms = round((monotonic() - started) * 1000)
        generated = normalize_export(json.loads(json.dumps(collect(session, trip_id), default=str)))
    engine.dispose()

    # Every place in the disposable DB came from the export or the place provider.
    candidate_ids = {row["place_id"] for row in generated["places"]}
    # Join the provider's per-call outcome (codes only) onto the timing rows.
    for diag in getattr(provider, "call_diagnostics", []):
        row = next((c for c in calls if c["call"] == diag["call"]), None)
        if row is not None:
            row.update({k: v for k, v in diag.items() if k not in ("call", "done_reason")})
    model_input = (candidate_diagnostics(captured["places"], trip_days, "candidates sent to the model", preferences)
                   if captured.get("places") is not None else None)
    warnings, score, score_v2 = review(generated, interests, travel_style)
    base_warnings, base_score, base_score_v2 = review(baseline_source, interests, travel_style)
    criticals = critical_errors(generated, candidate_ids, error)
    output_ms = sum(c.get("output_ms") or 0 for c in calls)
    result = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "trip_label": TRIP_LABELS[args.trip],
        "source_trip_id": int(source_id),
        "provider": args.provider,
        "model": meta,
        "isolated_target": {k: target[k] for k in ("host", "port", "database")},
        "error": error,
        "timing": {"total_generation_ms": total_ms, "ollama_output_ms": output_ms if calls else None,
                   "ollama_prompt_tokens": sum(c.get("prompt_tokens") or 0 for c in calls) if calls else None,
                   "ollama_output_tokens": sum(c.get("output_tokens") or 0 for c in calls) if calls else None,
                   "ollama_calls": len(calls)},
        "ollama_calls": calls,
        "candidate_diagnostics": {"seeded": seeded, "model_input": model_input},
        "service_warnings": response_warnings,
        "quality_warnings": [{"code": w.code, "severity": w.severity, "message": w.message} for w in warnings],
        "critical_errors": criticals,
        "score": score,
        "score_v2": score_v2,
        "score_v2_changes": V2_CHANGES,
        "candidate_mode": args.candidates,
        "candidate_source": candidate_source,
        "route_metrics": route_metrics(route_metadata, generated),
        # A short candidate pool is a supply problem, not a pass (Phase 3B).
        "supply_ok": bool(model_input) and not model_input["problems"],
        "passes_80": score_v2["total"] >= 80 and not criticals and bool(model_input) and not model_input["problems"],
        "passes_80_v1": score["total"] >= 80 and not criticals,
        "generated": generated,
        "model_input_place_ids": [place["place_id"] for place in captured.get("places") or []],
        "route_optimization": getattr(service, "last_route_optimization", None),
        "route_risk": route_risk(generated) if generated["plan_items"] else [],
        "baseline_route_risk": route_risk(baseline_source) if baseline_source["plan_items"] else [],
        "replay_source": args.replay,
        "baseline": {"manual_score": MANUAL_BASELINE.get(source_id, {}).get("score"), "manual_warnings": MANUAL_BASELINE.get(source_id, {}).get("warnings"),
                     "score": base_score, "score_v2": base_score_v2, "quality_warnings": [{"code": w.code, "message": w.message} for w in base_warnings],
                     "plan_items": baseline_source["plan_items"]},
        "limitations": [
            f"export에는 기존 일정에 쓰인 장소 {len(exported['places'])}곳만 있고, 당시 EXAONE에 전달된 전체 후보 목록은 없습니다.",
            f"후보 모드: {args.candidates} = {candidate_source}.",
            "route_provider=unavailable(기존과 동일)이라 이동시간은 실측되지 않습니다.",
            "장소 실존·영업시간은 확인하지 않았으며 정상으로 간주하지 않았습니다. 점수는 잠정입니다.",
            "자동 점수는 리뷰 문서 6.3 기준의 근사치입니다. 수동 점수(47/54)와 직접 비교하지 말고 같은 채점기로 계산한 기존 일정 점수와 비교하세요.",
            *(["Replay: 저장된 실제 EXAONE 일정을 다시 입력해 후처리만 비교합니다. 후보 풀은 그 실행의 DB 장소로 다시 계산되므로 당시 모델 입력과 완전히 같지 않을 수 있습니다. '기존 일정' 열은 그 실제 일정입니다."] if args.provider == "replay" else []),
        ] + (["Mock 모드: 네트워크 없는 가짜 Ollama 응답(1차는 일부러 중복 장소로 검증 실패, 2차 정상)이라 시간·토큰·점수는 품질 판단에 쓰지 않습니다."] if args.provider == "mock" else [])
          + (["fixture 장소는 합성([가상]) 데이터입니다. 공급 로직 검증용이며 품질 결과가 아닙니다."] if args.candidates == "fixture" else []),
    }
    out_dir = Path(args.out_dir) / f"{datetime.now():%Y%m%d_%H%M%S}_{args.trip}_{args.provider}_{args.candidates}"
    if result["route_optimization"]:
        ro = result["route_optimization"]
        print(f"route: applied={ro['applied']} moves={len(ro['moves'])} before_m={ro['before_m']} after_m={ro['after_m']} "
              f"longest_before_m={ro['longest_leg_before_m']} longest_after_m={ro['longest_leg_after_m']} rest_breaks={len(ro.get('rest_breaks', []))} reverted={ro.get('reverted') or ro.get('rest_reverted')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out_dir / "result.md").write_text(markdown(result), encoding="utf-8")
    print(f"result: error={error} total_ms={total_ms} score_v2={score_v2['total']} score_v1={score['total']} passes_80={result['passes_80']} "
          f"critical={len(criticals)} warnings={len(warnings)} baseline_v2={base_score_v2['total']} baseline_v1={base_score['total']}")
    if model_input:
        print(f"candidates sent to model: total={model_input['total']} sights={model_input['non_food']} restaurants={model_input['restaurants']} "
              f"areas={model_input['areas']} status={model_input['status']}")
    print(f"saved: {out_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UnsafeTarget as exc:
        print(f"ABORT (not an isolated database): {exc}", file=sys.stderr)
        raise SystemExit(3)
