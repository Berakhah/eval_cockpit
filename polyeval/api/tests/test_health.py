"""Smoke tests for health endpoints. Run via `pytest -q` inside the api container."""

from fastapi.testclient import TestClient

from polyeval_api.main import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["version"], str) and body["version"]


def test_readyz() -> None:
    client = TestClient(create_app())
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["checks"].keys()) == {"db", "redis", "scheduler"}


def test_metrics() -> None:
    client = TestClient(create_app())
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_openapi_emits_servable_document() -> None:
    """The codegen pipeline depends on a valid OpenAPI document at startup."""
    app = create_app()
    schema = app.openapi()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "PolyEval API"
    paths = schema["paths"]
    assert "/healthz" in paths
    assert "/readyz" in paths
