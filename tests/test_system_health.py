"""Tests for the /system/health endpoint using TestClient."""

from fastapi.testclient import TestClient
import os

from backend.api.app import app


def test_system_health_autostart(monkeypatch):
    # Ensure autostart for the test so kernel and market engine are started
    monkeypatch.setenv("HAGMARTK_AUTOSTART", "1")

    with TestClient(app) as client:
        resp = client.get("/system/health")
    assert resp.status_code == 200

    data = resp.json()
    assert "kernel" in data
    assert "engines" in data
    assert "eventbus" in data
    # symbol_count may be present for mock adapter
    assert "uptime_seconds" in data


def test_system_health_no_system(monkeypatch):
    # Simulate app without system by clearing state after startup
    with TestClient(app) as client:
        if hasattr(app.state, "system"):
            delattr(app.state, "system")

        resp = client.get("/system/health")
    # Expect 503 when system not initialized
    assert resp.status_code == 503
        # End of test_system_health_no_system