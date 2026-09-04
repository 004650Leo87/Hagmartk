from fastapi.testclient import TestClient

from backend.api.app import app
from backend.domain.shadow_models import HDFEvidence
from backend.services.hdf_event_adapter import HDFRadarAdapter


client = TestClient(app)


def make_live_evidence():
    return HDFEvidence(
        evidence_id="ev_api_live",
        symbol="USDCHF",
        timeframe="M15",
        asset_class="FOREX",
        direction="BEARISH",
        pivot_1_time="2026-09-04T00:30:00+00:00",
        pivot_1_price=0.8010,
        pivot_1_rsi=65.0,
        pivot_2_time="2026-09-04T01:00:00+00:00",
        pivot_2_price=0.8020,
        pivot_2_rsi=60.0,
        relative_volume=1.15,
        volume_pass=True,
        variant_stage="HDF_DV",
        source="LIVE_PROSPECTIVE",
        detected_at="2026-09-04T01:45:00+00:00",
    )


def test_event_radar_is_read_only_projection(monkeypatch):
    event = HDFRadarAdapter.build_radar(make_live_evidence())

    class FakeRadarService:
        def list_live_radar(self, limit=50):
            return [event]

    monkeypatch.setattr("backend.api.event_routes.HDFRadarService", FakeRadarService)
    response = client.get("/api/events/radar?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["event_class"] == "RADAR"
    assert payload[0]["publication_eligible"] is False
    assert payload[0]["reference_region"] is None
    assert payload[0]["invalidation_level"] is None
    assert payload[0]["objective_regions"] == []


def test_event_radar_rejects_write_methods():
    for method in (client.post, client.put, client.delete):
        response = method("/api/events/radar")
        assert response.status_code == 405


def test_event_radar_limit_validation():
    assert client.get("/api/events/radar?limit=0").status_code == 422
    assert client.get("/api/events/radar?limit=201").status_code == 422
