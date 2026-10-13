import importlib

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.config import DatabaseNotConfiguredError, Settings
from app.core.exceptions import AppError, register_exception_handlers


def test_application_import_and_health_without_mysql(client):
    module = importlib.import_module("app.main")
    assert isinstance(module.app, FastAPI)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_logging_is_sanitised_and_returns_request_id(client, caplog):
    caplog.set_level("INFO", logger="app.http")
    response = client.get("/api/v1/health", headers={
        "X-Request-ID": "http-contract-test",
        "Authorization": "Bearer must-not-be-logged",
    })
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "http-contract-test"
    record = next(row.getMessage() for row in caplog.records if "http_request" in row.getMessage())
    assert "request_id=http-contract-test" in record
    assert "method=GET" in record and "endpoint=/api/v1/health" in record and "status=200" in record
    assert "must-not-be-logged" not in record


def test_docs_include_task_three_endpoints(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = set(schema.json()["paths"])
    assert {"/api/v1/auth/social-login", "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/naver/authorize", "/api/v1/auth/naver/login"} <= paths


@pytest.mark.parametrize("method,path,status,code", [
    ("GET", "/api/v1/missing", 404, "NOT_FOUND"),
    ("POST", "/api/v1/health", 405, "METHOD_NOT_ALLOWED"),
])
def test_framework_errors_use_common_envelope(client, method, path, status, code):
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert isinstance(response.json()["error"]["message"], str)


@pytest.mark.parametrize("origin,allowed", [
    ("https://frontend.example", True),
    ("http://localhost:8080", True),
    ("https://untrusted.example", False),
])
def test_cors_preflight_and_actual_response(origin, allowed):
    from app.main import create_app

    settings = Settings(cors_allowed_origins="https://frontend.example, http://localhost:8080")
    with TestClient(create_app(settings)) as client:
        response = client.options("/api/v1/health", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        })
        assert response.status_code == (200 if allowed else 400)
        assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
        actual = client.get("/api/v1/health", headers={"Origin": origin})
        assert actual.status_code == 200
        assert actual.headers.get("access-control-allow-origin") == (origin if allowed else None)


def test_empty_cors_does_not_allow_arbitrary_origin(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_all_exception_handlers_and_no_raw_details():
    # Test-only routes do not become part of the production application.
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app")
    def app_error():
        raise AppError("EXAMPLE_ERROR", "Expected public message", 409)

    @app.get("/validation")
    def validation(count: int):
        return count

    @app.get("/http")
    def http_error():
        raise HTTPException(401, "private-detail", headers={"WWW-Authenticate": "Bearer"})

    @app.get("/db")
    def db_error():
        raise DatabaseNotConfiguredError("private-detail")

    @app.get("/unexpected")
    def unexpected_error():
        raise RuntimeError("private-detail")

    cases = [
        ("/app", 409, "EXAMPLE_ERROR"),
        ("/validation?count=private-detail", 422, "VALIDATION_ERROR"),
        ("/http", 401, "UNAUTHORIZED"),
        ("/db", 503, "DATABASE_NOT_CONFIGURED"),
        ("/unexpected", 500, "INTERNAL_SERVER_ERROR"),
    ]
    with TestClient(app, raise_server_exceptions=False) as client:
        for path, status, code in cases:
            response = client.get(path)
            assert response.status_code == status
            assert response.json()["error"]["code"] == code
            assert "private-detail" not in response.text
        assert client.get("/http").headers["WWW-Authenticate"] == "Bearer"
