from fastapi.testclient import TestClient

from backend.api.app import app


client = TestClient(app)


def test_strategy_registry_api_exposes_only_product_contracts():
    response = client.get("/api/registry/strategies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    by_id = {item["strategy_id"]: item for item in payload["strategies"]}
    assert set(by_id) == {"hagmartk_divergence_flow", "cycle_theory_v111_fidelity"}
    assert by_id["hagmartk_divergence_flow"]["stage"] == "SHADOW"
    assert by_id["hagmartk_divergence_flow"]["real_order_execution_allowed"] is False
    assert by_id["cycle_theory_v111_fidelity"]["stage"] == "SHADOW"
    assert by_id["cycle_theory_v111_fidelity"]["candidate_id"] == "cycle_theory_v111_baseline"
    assert len(by_id["cycle_theory_v111_fidelity"]["parameter_hash"]) == 64


def test_evidence_registry_api_exposes_declared_contracts():
    response = client.get("/api/registry/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    keys = {item["evidence_key"] for item in payload["evidence"]}
    assert keys == {
        "HDF_SHADOW_EVIDENCE_V1",
        "HDF_FIBONACCI_RESEARCH_V1",
        "CYCLE_THEORY_V111_FIDELITY_EVIDENCE",
        "CYCLE_THEORY_V111_SHADOW_EVIDENCE",
    }


def test_event_protocol_api_is_read_only_and_execution_disabled():
    response = client.get("/api/registry/event-protocol")
    assert response.status_code == 200
    payload = response.json()
    assert payload["lifecycle"] == ["DETECTED", "FORMING", "CONFIRMED", "ACTIVE", "RESOLVED"]
    assert "QUANT_EVENT" in payload["event_classes"]
    assert payload["publication_adapters_enabled"] is False
    assert payload["real_order_execution_enabled"] is False


def test_registry_routes_are_get_only():
    for path in (
        "/api/registry/strategies",
        "/api/registry/evidence",
        "/api/registry/event-protocol",
    ):
        assert client.post(path).status_code == 405
        assert client.put(path).status_code == 405
        assert client.delete(path).status_code == 405
