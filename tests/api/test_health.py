import logging

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok_and_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_every_request_is_access_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.access")
    with TestClient(app) as client:
        client.get("/health")
    assert "GET /health -> 200" in caplog.text


def test_root_serves_the_frontend_integration_guide() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Frontend integration guide" in response.text
