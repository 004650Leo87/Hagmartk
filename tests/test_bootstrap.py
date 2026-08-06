"""Tests for the controlled bootstrap module.

These tests run in mock adapter mode and do not require MT5.
"""

import os

from backend.bootstrap import create_system, start_system, shutdown_system
from backend.kernel.engine_status import EngineStatus


def test_mock_bootstrap_startup_and_shutdown(monkeypatch):
    monkeypatch.setenv("HAGMARTK_MARKET_ADAPTER", "mock")

    system = create_system()
    assert system["adapter_mode"] == "mock"

    start_system(system)

    application = system["application"]
    status = application.system_status()

    assert status["kernel"] == EngineStatus.RUNNING
    assert "MarketEngine" in status["engines"]
    assert status["engines"]["MarketEngine"] == EngineStatus.RUNNING

    shutdown_system(system)
    status_after = application.system_status()
    assert status_after["kernel"] in (EngineStatus.STOPPED, EngineStatus.FAILED)


def test_adapter_selection_invalid(monkeypatch):
    monkeypatch.setenv("HAGMARTK_MARKET_ADAPTER", "invalid_adapter")
    try:
        create_system()
        assert False, "create_system should have raised for invalid adapter"
    except ValueError:
        pass
