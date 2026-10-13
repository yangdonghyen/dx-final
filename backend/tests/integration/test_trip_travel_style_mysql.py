"""Opt-in API-to-DB coverage for trip-scoped travel styles.

The suite requires the same launcher-verified, disposable MySQL instance as
the preview integration tests. It never uses a developer's configured MySQL.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pymysql
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models.trip import Trip, TripPreference
from app.models.user import User
from app.services.plan_generation_service import PlanGenerationService


pytestmark = pytest.mark.mysql_integration
_REAL_PYMYSQL_CONNECT = pymysql.connect


@pytest.fixture
def trip_style_mysql_engine(monkeypatch):
    """Connect only after proving the configured target is disposable."""
    raw_url = os.environ.get("PLAN_REGENERATION_MYSQL_TEST_URL")
    expected_datadir = os.environ.get("PLAN_REGENERATION_MYSQL_TEST_DATADIR")
    if not raw_url or not expected_datadir:
        pytest.skip("isolated MySQL launcher variables are required")

    url = make_url(raw_url)
    if (
        not url.drivername.startswith("mysql")
        or url.host != "127.0.0.1"
        or not url.port
        or url.port == 3306
        or "test" not in (url.database or "").lower()
    ):
        pytest.fail("trip style integration requires a loopback, non-3306 test database")

    monkeypatch.setattr(pymysql, "connect", _REAL_PYMYSQL_CONNECT)
    verification_engine = create_engine(url, pool_pre_ping=True)
    try:
        with verification_engine.connect() as connection:
            actual_datadir = connection.scalar(text("SELECT @@datadir"))
            actual_port = connection.scalar(text("SELECT @@port"))
            actual_database = connection.scalar(text("SELECT DATABASE()"))
    finally:
        verification_engine.dispose()
    if (
        actual_port != url.port
        or actual_database != url.database
        or Path(actual_datadir).resolve() != Path(expected_datadir).resolve()
    ):
        pytest.fail("trip style integration target is not the declared isolated instance")

    monkeypatch.setenv("MYSQL_HOST", url.host)
    monkeypatch.setenv("MYSQL_PORT", str(url.port))
    monkeypatch.setenv("MYSQL_DATABASE", url.database)
    monkeypatch.setenv("MYSQL_USER", url.username or "")
    monkeypatch.setenv("MYSQL_PASSWORD", url.password or "")
    monkeypatch.setenv("JWT_SECRET_KEY", "trip-style-isolated-test-secret")
    get_settings.cache_clear()
    command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
    engine = create_engine(url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def trip_style_client(trip_style_mysql_engine):
    def database_session():
        session = Session(trip_style_mysql_engine)
        try:
            yield session
        finally:
            session.close()

    application = create_app(get_settings())
    application.dependency_overrides[get_db] = database_session
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


def _create_user(engine, suffix):
    with Session(engine) as session:
        user = User(nickname=f"trip-style-{suffix}")
        session.add(user)
        session.commit()
        return user.user_id


def _delete_user(engine, user_id):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is not None:
            session.delete(user)
            session.commit()


def _headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _create_payload(style=None):
    payload = {
        "title": "Isolated trip style",
        "destination": "Busan",
        "start_date": "2026-10-10",
        "end_date": "2026-10-11",
        "transport_mode": "CAR",
        "companion_ids": [],
        "interest_codes": [],
    }
    if style is not None:
        payload["trip_preferences"] = {"travel_style": style}
    return payload


def _stored_style(engine, trip_id):
    with Session(engine) as session:
        preference = session.scalar(
            select(TripPreference).where(TripPreference.trip_id == trip_id)
        )
        return preference.travel_style if preference is not None else None


def _generation_input_style(engine, trip_id):
    with Session(engine) as session:
        trip = session.get(Trip, trip_id)
        generation = PlanGenerationService(session, provider=object())
        # The test's responsibility is the persisted preference read. Candidate
        # discovery is intentionally replaced so no place provider can run.
        generation._candidate_places = lambda *_args: []
        _, preferences, *_ = generation._input(trip)
        return preferences["travel_style"]


@pytest.mark.parametrize("style", ["SLOW", "STANDARD", "FOOD_FOCUSED"])
def test_create_get_and_generation_input_preserve_each_trip_style(
    trip_style_client, trip_style_mysql_engine, style,
):
    user_id = _create_user(trip_style_mysql_engine, style.lower())
    try:
        created = trip_style_client.post(
            "/api/v1/trips", headers=_headers(user_id), json=_create_payload(style),
        )
        assert created.status_code == 201, created.json()
        trip_id = created.json()["trip_id"]

        assert _stored_style(trip_style_mysql_engine, trip_id) == style
        detail = trip_style_client.get(f"/api/v1/trips/{trip_id}", headers=_headers(user_id))
        assert detail.status_code == 200
        assert detail.json()["preferences"]["travel_style"] == style
        assert _generation_input_style(trip_style_mysql_engine, trip_id) == style
    finally:
        _delete_user(trip_style_mysql_engine, user_id)


def test_trip_styles_are_isolated_per_trip(trip_style_client, trip_style_mysql_engine):
    user_id = _create_user(trip_style_mysql_engine, "isolation")
    try:
        slow = trip_style_client.post("/api/v1/trips", headers=_headers(user_id), json=_create_payload("SLOW"))
        food = trip_style_client.post("/api/v1/trips", headers=_headers(user_id), json=_create_payload("FOOD_FOCUSED"))
        assert slow.status_code == food.status_code == 201

        slow_id, food_id = slow.json()["trip_id"], food.json()["trip_id"]
        assert _stored_style(trip_style_mysql_engine, slow_id) == "SLOW"
        assert _stored_style(trip_style_mysql_engine, food_id) == "FOOD_FOCUSED"
        assert _generation_input_style(trip_style_mysql_engine, slow_id) == "SLOW"
        assert _generation_input_style(trip_style_mysql_engine, food_id) == "FOOD_FOCUSED"
    finally:
        _delete_user(trip_style_mysql_engine, user_id)


def test_invalid_trip_style_is_rejected_without_creating_a_trip(trip_style_client, trip_style_mysql_engine):
    user_id = _create_user(trip_style_mysql_engine, "invalid")
    try:
        with Session(trip_style_mysql_engine) as session:
            before = len(session.scalars(select(Trip).where(Trip.user_id == user_id)).all())
        response = trip_style_client.post(
            "/api/v1/trips", headers=_headers(user_id), json=_create_payload("RELAXED"),
        )
        assert response.status_code == 422
        with Session(trip_style_mysql_engine) as session:
            after = len(session.scalars(select(Trip).where(Trip.user_id == user_id)).all())
        assert after == before
    finally:
        _delete_user(trip_style_mysql_engine, user_id)


def test_legacy_create_without_trip_style_remains_supported(trip_style_client, trip_style_mysql_engine):
    user_id = _create_user(trip_style_mysql_engine, "legacy")
    try:
        response = trip_style_client.post(
            "/api/v1/trips", headers=_headers(user_id), json=_create_payload(),
        )
        assert response.status_code == 201
        trip_id = response.json()["trip_id"]
        assert _stored_style(trip_style_mysql_engine, trip_id) is None
        detail = trip_style_client.get(f"/api/v1/trips/{trip_id}", headers=_headers(user_id))
        assert detail.status_code == 200
        assert detail.json()["preferences"]["travel_style"] is None
    finally:
        _delete_user(trip_style_mysql_engine, user_id)
