"""Tests for the /system/health endpoint using TestClient."""

from fastapi.testclient import TestClient
import os

from backend.api.app import app


def test_system_health_autostart(monkeypatch):
    # Explicit autostart is tested with mock market data and a no-op scanner.
    monkeypatch.setenv("HAGMARTK_AUTOSTART", "1")
    monkeypatch.setenv("HAGMARTK_MARKET_ADAPTER", "mock")

    class FakeScanner:
        def start_auto_scheduler(self, adapter, interval_seconds=3.0):
            self.started = True

        def stop_auto_scheduler(self):
            self.started = False

    monkeypatch.setattr(
        "backend.services.shadow_scanner.ShadowScannerManager",
        lambda: FakeScanner(),
    )

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

def test_system_default_does_not_autostart(monkeypatch):
    """Imports/TestClient must not start the real kernel unless explicitly requested."""
    monkeypatch.delenv("HAGMARTK_AUTOSTART", raising=False)

    with TestClient(app):
        assert app.state.system is not None
        assert app.state.started_at is None
