import os

import pymysql
import pytest

from app.core.config import Settings, get_settings
from app.db.session import get_engine, get_session_factory


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    """Tests never use a developer's .env or open a real MySQL connection."""
    for name in os.environ:
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    def forbid_connection(*args, **kwargs):
        pytest.fail("Phase 0 tests must not connect to MySQL")

    monkeypatch.setattr(pymysql, "connect", forbid_connection)
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(Settings(_env_file=None))) as test_client:
        yield test_client
