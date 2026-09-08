from fastapi.testclient import TestClient

from backend.api.app import app
from backend.strategies.orb.config import ORB_V1_CONFIG_HASH

client = TestClient(app)


def test_orb_status_is_validation_paper_only():
    payload = client.get("/api/orb/status").json()
    assert payload["display_name"] == "ORB"
    assert payload["stage"] == "VALIDATION"
    assert payload["config_hash"] == ORB_V1_CONFIG_HASH
    assert payload["engine_core_ready"] is True
    assert payload["prospective_shadow_enabled"] is False
    assert payload["real_order_execution_enabled"] is False


def test_orb_config_is_frozen_v1():
    payload = client.get("/api/orb/config").json()
    params = payload["parameters"]
    assert params["opening_range_minutes"] == 15
    assert params["signal_timeframe_minutes"] == 5
    assert params["target_r_multiple"] == "2"
    assert params["risk_fraction"] == "0.0025"


def test_orb_profiles_are_explicit_and_empty_by_default():
    payload = client.get("/api/orb/session-profiles").json()
    assert payload["policy"] == "EXPLICIT_ONLY_NO_UNIVERSAL_OPEN_ASSUMPTION"
    assert payload["count"] == 0
    assert payload["profiles"] == []


def test_orb_tradingview_surface_is_signal_conformance_only():
    payload = client.get("/api/orb/tradingview").json()
    assert payload["name"] == "ORB"
    assert payload["role"] == "SIGNAL_CONFORMANCE_VISUALIZATION"
    assert payload["canonical_execution_ledger"] == "HAGMARTK"
    assert payload["real_order_execution_enabled"] is False
