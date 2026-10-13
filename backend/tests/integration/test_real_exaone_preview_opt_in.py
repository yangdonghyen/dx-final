"""Opt-in FastAPI + real EXAONE verification against the disposable MySQL server.

This test never runs in the normal integration suite.  The launcher must set
RUN_REAL_EXAONE_PREVIEW=1 after it has created and verified an isolated MySQL
instance.
"""

from datetime import date, time
import os
from time import monotonic

import pytest
import pymysql
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.v1 import plans as plan_routes
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.place import Place
from app.models.plan import PlanItem, PlanRegenerationPreview, TravelPlan
from app.models.trip import Trip, TripSelectedPlace
from app.models.user import User
from app.repositories.plan_repository import PlanItemRepository
from app.services.external.factory import get_plan_generation_provider
from app.services.plan_regeneration_approval_service import PlanRegenerationApprovalService
from app.services.plan_regeneration_preview_service import PlanRegenerationPreviewService


pytestmark = pytest.mark.mysql_integration
_REAL_PYMYSQL_CONNECT = pymysql.connect


def _enabled():
    return os.environ.get("RUN_REAL_EXAONE_PREVIEW") == "1"


def _real_ai_timeout_seconds():
    """Per Ollama call; REAL_EXAONE_AI_TIMEOUT_SECONDS overrides the 180s default."""
    return os.environ.get("REAL_EXAONE_AI_TIMEOUT_SECONDS", "180")


def _scenario_enabled(name):
    """REAL_EXAONE_SCENARIO=places|rest runs one real-model scenario; default all."""
    selected = os.environ.get("REAL_EXAONE_SCENARIO", "all").strip().lower()
    return selected in {"all", name}


@pytest.fixture
def mysql_engine(monkeypatch):
    """Open only the launcher-verified, disposable loopback database."""
    raw_url = os.environ.get("PLAN_REGENERATION_MYSQL_TEST_URL")
    expected_datadir = os.environ.get("PLAN_REGENERATION_MYSQL_TEST_DATADIR")
    if not raw_url or not expected_datadir:
        pytest.skip("isolated MySQL launcher variables are required")
    url = make_url(raw_url)
    assert url.host == "127.0.0.1" and url.port not in {None, 3306}
    assert "test" in (url.database or "").lower()
    monkeypatch.setattr(pymysql, "connect", _REAL_PYMYSQL_CONNECT)
    engine = create_engine(url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_real_exaone_preview_http_approve_on_isolated_mysql(mysql_engine, monkeypatch, caplog):
    if not _enabled():
        pytest.skip("RUN_REAL_EXAONE_PREVIEW=1 is required")
    if not _scenario_enabled("places"):
        pytest.skip("REAL_EXAONE_SCENARIO excludes places")

    from app.services.external.routing import UnavailableRouteProvider

    monkeypatch.setenv("PLAN_PROVIDER", "real")
    monkeypatch.setenv("PLACE_PROVIDER", "mock")
    monkeypatch.setenv("ROUTE_PROVIDER", "unavailable")
    monkeypatch.setenv("JWT_SECRET_KEY", "task75d-isolated-http-secret")
    monkeypatch.setenv("EXAONE_BASE_URL", os.environ["TASK75D_EXAONE_BASE_URL"])
    monkeypatch.setenv("EXAONE_MODEL", os.environ["TASK75D_EXAONE_MODEL"])
    # tests/conftest.py disables .env, so the 60s code default would apply.
    # Only this opt-in real-model test raises the per-call Ollama timeout.
    monkeypatch.setenv("AI_API_TIMEOUT_SECONDS", _real_ai_timeout_seconds())
    get_settings.cache_clear()
    settings = get_settings()
    provider = get_plan_generation_provider(settings)
    assert provider.model == settings.exaone_model
    assert provider.client.timeout == float(_real_ai_timeout_seconds())

    with Session(mysql_engine) as session:
        user = User(nickname="task75d-real-exaone")
        places = [
            Place(name="Task75D Haeundae", category="AT4 관광명소", region="부산", address="부산광역시 해운대구", latitude=35.1587, longitude=129.1604),
            Place(name="Task75D Gwangalli", category="AT4 관광명소", region="부산", address="부산광역시 수영구", latitude=35.1532, longitude=129.1186),
            Place(name="Task75D Gamcheon", category="AT4 관광명소", region="부산", address="부산광역시 사하구", latitude=35.0975, longitude=129.0106),
        ]
        session.add(user); session.add_all(places); session.flush()
        trip = Trip(user_id=user.user_id, title="Task75D Busan", destination="부산", start_date=date(2026, 10, 10), end_date=date(2026, 10, 10), transport_mode="WALK")
        session.add(trip); session.flush()
        session.add(TripSelectedPlace(trip_id=trip.trip_id, place_id=places[0].place_id, selected_order=1))
        plan = TravelPlan(trip_id=trip.trip_id, status="DRAFT", current_version=1)
        session.add(plan); session.flush()
        for sequence, place in enumerate(places, start=1):
            PlanItemRepository(session).create(plan.plan_id, place_id=place.place_id, visit_date=date(2026, 10, 10), sequence_no=sequence, item_type="PLACE", title=place.name, start_time=time(9 + sequence), end_time=time(10 + sequence), recommendation_reason="original", validation_status="UNKNOWN")
        session.commit()
        user_id, plan_id, anchor_id = user.user_id, plan.plan_id, places[0].place_id
        candidate_rows = [{"place_id": place.place_id, "name": place.name, "category": place.category, "region": place.region, "address": place.address, "latitude": place.latitude, "longitude": place.longitude, "is_anchor": place.place_id == anchor_id} for place in places]
        candidate_map = {place.place_id: place for place in places}

    trip_input = {"destination": "부산", "start_date": date(2026, 10, 10), "end_date": date(2026, 10, 10), "budget_krw": 300000, "transport_mode": "WALK"}
    inputs = (trip_input, {"walking_tolerance": "LOW", "rest_frequency": "HIGH"}, [], ["CULTURE"], {"raw_interest_codes": []}, candidate_rows, {anchor_id}, candidate_map)

    def configure(service):
        service.generation._input = lambda _trip: inputs

    def preview_service():
        session = Session(mysql_engine)
        service = PlanRegenerationPreviewService(session, provider, route_provider=UnavailableRouteProvider())
        configure(service)
        try:
            yield service
        finally:
            session.close()

    def approval_service():
        session = Session(mysql_engine)
        service = PlanRegenerationApprovalService(session, provider, route_provider=UnavailableRouteProvider())
        configure(service)
        try:
            yield service
        finally:
            session.close()

    def database_session():
        session = Session(mysql_engine)
        try:
            yield session
        finally:
            session.close()

    application = create_app(settings)
    application.dependency_overrides[get_db] = database_session
    application.dependency_overrides[plan_routes.get_preview_service] = preview_service
    application.dependency_overrides[plan_routes.get_approval_service] = approval_service
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}", "X-Request-ID": "task75d-real-exaone"}
    started_at = monotonic()
    try:
        with TestClient(application) as client:
            before = client.get(f"/api/v1/plans/{plan_id}", headers=headers)
            assert before.status_code == 200 and before.json()["current_version"] == 1
            preview = client.post(f"/api/v1/plans/{plan_id}/regeneration-previews", headers=headers, json={"reason": "USER_FATIGUE", "instruction": "Reduce optional activity places while keeping the required anchor.", "feedback_codes": ["places"]})
            assert preview.status_code == 200, preview.json().get("error", {}).get("code")
            preview_id = preview.json()["preview_id"]
            with Session(mysql_engine) as observer:
                pending = observer.get(PlanRegenerationPreview, preview_id)
                assert pending.status == "PENDING"
                assert observer.get(TravelPlan, plan_id).current_version == 1
                assert len(PlanItemRepository(observer).list(plan_id)) == 3
                proposed_ids = {item["place_id"] for item in pending.proposed_itinerary["items"] if item["place_id"] is not None}
                assert anchor_id in proposed_ids and len(proposed_ids) < 3
            approved = client.post(f"/api/v1/plans/{plan_id}/regeneration-previews/{preview_id}/approve", headers=headers)
            assert approved.status_code == 200 and approved.json()["current_version"] == 2
            with Session(mysql_engine) as observer:
                assert observer.get(TravelPlan, plan_id).current_version == 2
                assert anchor_id in {item.place_id for item in observer.query(PlanItem).filter_by(plan_id=plan_id).all()}
            print(f"REAL_EXAONE_RESULT model={settings.exaone_model} http_preview=200 http_approve=200 elapsed_ms={round((monotonic() - started_at) * 1000)} retry_observed={'preview_feedback_goal request_id=task75d-real-exaone plan_id=' in caplog.text and 'result=RETRYING' in caplog.text}")
    finally:
        application.dependency_overrides.clear()
        with Session(mysql_engine) as session:
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
            for place_id in candidate_map:
                place = session.get(Place, place_id)
                if place is not None:
                    session.delete(place)
            session.commit()
        get_settings.cache_clear()



def test_real_exaone_rest_preview_http_approve_on_isolated_mysql(mysql_engine, monkeypatch, caplog):
    """NOT_ENOUGH_REST ("rest"): REST minutes must rise, anchor stays, preview waits for approval."""
    if not _enabled():
        pytest.skip("RUN_REAL_EXAONE_PREVIEW=1 is required")
    if not _scenario_enabled("rest"):
        pytest.skip("REAL_EXAONE_SCENARIO excludes rest")

    import logging

    from app.services.external.routing import UnavailableRouteProvider

    caplog.set_level(logging.INFO)
    monkeypatch.setenv("PLAN_PROVIDER", "real")
    monkeypatch.setenv("PLACE_PROVIDER", "mock")
    monkeypatch.setenv("ROUTE_PROVIDER", "unavailable")
    monkeypatch.setenv("JWT_SECRET_KEY", "task75e-isolated-http-secret")
    monkeypatch.setenv("EXAONE_BASE_URL", os.environ["TASK75D_EXAONE_BASE_URL"])
    monkeypatch.setenv("EXAONE_MODEL", os.environ["TASK75D_EXAONE_MODEL"])
    # tests/conftest.py disables .env, so the 60s code default would apply.
    # Only this opt-in real-model test raises the per-call Ollama timeout.
    monkeypatch.setenv("AI_API_TIMEOUT_SECONDS", _real_ai_timeout_seconds())
    get_settings.cache_clear()
    settings = get_settings()
    provider = get_plan_generation_provider(settings)
    assert provider.model == settings.exaone_model
    assert provider.client.timeout == float(_real_ai_timeout_seconds())

    # Count real model calls (schema retries included) without changing them.
    model_calls = []
    real_chat = provider.client.chat

    def counted_chat(**kwargs):
        model_calls.append(monotonic())
        return real_chat(**kwargs)

    monkeypatch.setattr(provider.client, "chat", counted_chat)

    visit_date = date(2026, 10, 10)
    with Session(mysql_engine) as session:
        user = User(nickname="task75e-real-exaone-rest")
        places = [
            Place(name="Task75E Haeundae", category="AT4 관광명소", region="부산", address="부산광역시 해운대구", latitude=35.1587, longitude=129.1604),
            Place(name="Task75E Gwangalli", category="AT4 관광명소", region="부산", address="부산광역시 수영구", latitude=35.1532, longitude=129.1186),
            Place(name="Task75E Gamcheon", category="AT4 관광명소", region="부산", address="부산광역시 사하구", latitude=35.0975, longitude=129.0106),
        ]
        session.add(user); session.add_all(places); session.flush()
        trip = Trip(user_id=user.user_id, title="Task75E Busan", destination="부산", start_date=visit_date, end_date=visit_date, transport_mode="WALK")
        session.add(trip); session.flush()
        session.add(TripSelectedPlace(trip_id=trip.trip_id, place_id=places[0].place_id, selected_order=1))
        plan = TravelPlan(trip_id=trip.trip_id, status="DRAFT", current_version=1)
        session.add(plan); session.flush()
        # Back-to-back visits with no REST: the original plan has 0 REST minutes.
        for sequence, place in enumerate(places, start=1):
            PlanItemRepository(session).create(plan.plan_id, place_id=place.place_id, visit_date=visit_date, sequence_no=sequence, item_type="PLACE", title=place.name, start_time=time(9 + sequence), end_time=time(10 + sequence), recommendation_reason="original", validation_status="UNKNOWN")
        session.commit()
        user_id, plan_id, anchor_id = user.user_id, plan.plan_id, places[0].place_id
        candidate_rows = [{"place_id": place.place_id, "name": place.name, "category": place.category, "region": place.region, "address": place.address, "latitude": place.latitude, "longitude": place.longitude, "is_anchor": place.place_id == anchor_id} for place in places]
        candidate_map = {place.place_id: place for place in places}
        original_items = [(item.sequence_no, item.item_type, item.place_id, item.start_time, item.end_time) for item in PlanItemRepository(session).list(plan_id)]

    trip_input = {"destination": "부산", "start_date": visit_date, "end_date": visit_date, "budget_krw": 300000, "transport_mode": "WALK"}
    inputs = (trip_input, {"walking_tolerance": "LOW", "rest_frequency": "HIGH"}, [], ["CULTURE"], {"raw_interest_codes": []}, candidate_rows, {anchor_id}, candidate_map)

    def configure(service):
        service.generation._input = lambda _trip: inputs

    def preview_service():
        session = Session(mysql_engine)
        service = PlanRegenerationPreviewService(session, provider, route_provider=UnavailableRouteProvider())
        configure(service)
        try:
            yield service
        finally:
            session.close()

    def approval_service():
        session = Session(mysql_engine)
        service = PlanRegenerationApprovalService(session, provider, route_provider=UnavailableRouteProvider())
        configure(service)
        try:
            yield service
        finally:
            session.close()

    def database_session():
        session = Session(mysql_engine)
        try:
            yield session
        finally:
            session.close()

    def rest_minutes(items):
        return PlanRegenerationPreviewService._rest_minutes(items)

    application = create_app(settings)
    application.dependency_overrides[get_db] = database_session
    application.dependency_overrides[plan_routes.get_preview_service] = preview_service
    application.dependency_overrides[plan_routes.get_approval_service] = approval_service
    headers = {"Authorization": f"Bearer {create_access_token(str(user_id))}", "X-Request-ID": "task75e-real-exaone-rest"}
    started_at = monotonic()
    try:
        with TestClient(application) as client:
            before = client.get(f"/api/v1/plans/{plan_id}", headers=headers)
            assert before.status_code == 200 and before.json()["current_version"] == 1
            preview_started_at = monotonic()
            preview = client.post(f"/api/v1/plans/{plan_id}/regeneration-previews", headers=headers, json={"reason": "USER_FATIGUE", "instruction": "Add more REST time between activities while keeping the required anchor.", "feedback_codes": ["rest"]})
            preview_ms = round((monotonic() - preview_started_at) * 1000)
            preview_model_calls = len(model_calls)
            assert preview.status_code == 200, preview.json().get("error", {}).get("code")
            assert 1 <= preview_model_calls <= 4
            preview_id = preview.json()["preview_id"]
            with Session(mysql_engine) as observer:
                pending = observer.get(PlanRegenerationPreview, preview_id)
                assert pending.status == "PENDING"
                current_items = pending.current_itinerary_snapshot["items"]
                proposed_items = pending.proposed_itinerary["items"]
                rest_before, rest_after = rest_minutes(current_items), rest_minutes(proposed_items)
                assert rest_after > rest_before
                assert anchor_id in {item["place_id"] for item in proposed_items if item["place_id"] is not None}
                # Before approval the stored itinerary is untouched.
                assert observer.get(TravelPlan, plan_id).current_version == 1
                assert [(item.sequence_no, item.item_type, item.place_id, item.start_time, item.end_time) for item in PlanItemRepository(observer).list(plan_id)] == original_items
            approved = client.post(f"/api/v1/plans/{plan_id}/regeneration-previews/{preview_id}/approve", headers=headers)
            assert approved.status_code == 200 and approved.json()["current_version"] == 2
            with Session(mysql_engine) as observer:
                assert observer.get(TravelPlan, plan_id).current_version == 2
                stored = observer.query(PlanItem).filter_by(plan_id=plan_id).all()
                assert anchor_id in {item.place_id for item in stored}
                assert any(item.item_type == "REST" for item in stored)
            retry_observed = "result=RETRYING" in caplog.text and "task75e-real-exaone-rest" in caplog.text
            print(
                f"REAL_EXAONE_REST_RESULT model={settings.exaone_model} http_preview=200 http_approve=200 "
                f"rest_minutes_before={rest_before:g} rest_minutes_after={rest_after:g} "
                f"model_calls={preview_model_calls} retry_observed={retry_observed} "
                f"preview_ms={preview_ms} elapsed_ms={round((monotonic() - started_at) * 1000)}"
            )
    finally:
        application.dependency_overrides.clear()
        with Session(mysql_engine) as session:
            user = session.get(User, user_id)
            if user is not None:
                session.delete(user)
            for place_id in candidate_map:
                place = session.get(Place, place_id)
                if place is not None:
                    session.delete(place)
            session.commit()
        get_settings.cache_clear()
