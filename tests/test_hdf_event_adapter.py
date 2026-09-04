from backend.domain.market_events import MarketEventClass
from backend.domain.shadow_models import HDFEvidence
from backend.services.hdf_event_adapter import HDFRadarAdapter, HDFRadarService
from backend.services.shadow_store import ShadowStoreRepository


def make_evidence(evidence_id="ev_live", source="LIVE_PROSPECTIVE", is_test=False, stage="HDF_DV"):
    return HDFEvidence(
        evidence_id=evidence_id,
        symbol="USDCHF",
        timeframe="M15",
        asset_class="FOREX",
        direction="BEARISH",
        pivot_1_time="2026-09-04T00:30:00+00:00",
        pivot_1_price=0.8010,
        pivot_1_rsi=65.0,
        pivot_2_time={"ev_live":"2026-09-04T01:00:00+00:00","ev_hist":"2026-09-04T01:15:00+00:00","ev_test":"2026-09-04T01:30:00+00:00"}.get(evidence_id,"2026-09-04T01:00:00+00:00"),
        pivot_2_price=0.8020,
        pivot_2_rsi=60.0,
        relative_volume=1.15,
        volume_pass=True,
        pattern_type="NONE",
        pattern_pass=False,
        variant_stage=stage,
        source=source,
        is_test=is_test,
        detected_at="2026-09-04T01:45:00+00:00",
    )

def test_hdf_dv_becomes_radar_without_trade_structure():
    event = HDFRadarAdapter.build_radar(make_evidence())
    assert event.event_class == MarketEventClass.RADAR
    assert event.asset == "USDCHF"
    assert event.timeframe == "M15"
    assert event.reference_region is None
    assert event.invalidation_level is None
    assert event.objective_regions == ()
    assert event.publication_eligible is False
    assert dict(event.metadata)["hdf_variant_stage"] == "HDF_DV"


def test_radar_event_id_is_deterministic():
    first = HDFRadarAdapter.build_radar(make_evidence())
    second = HDFRadarAdapter.build_radar(make_evidence())
    assert first.event_id == second.event_id


def test_adapter_rejects_non_live_and_test_evidence():
    for evidence in (
        make_evidence(source="HISTORICAL_BACKFILL"),
        make_evidence(is_test=True),
    ):
        try:
            HDFRadarAdapter.to_observation(evidence)
        except ValueError:
            pass
        else:
            raise AssertionError("non-live/test evidence must be rejected")

def test_service_reads_only_live_non_test_evidence(tmp_path):
    db_path = tmp_path / "shadow_test.db"
    repo = ShadowStoreRepository(str(db_path))
    repo.save_hdf_evidence(make_evidence("ev_live"))
    repo.save_hdf_evidence(make_evidence("ev_hist", source="HISTORICAL_BACKFILL"))
    repo.save_hdf_evidence(make_evidence("ev_test", source="TEST", is_test=True))

    events = HDFRadarService(repository=repo).list_live_radar(limit=20)
    assert len(events) == 1
    event = events[0]
    assert dict(event.metadata)["hdf_evidence_id"] == "ev_live"
    assert event.event_class == MarketEventClass.RADAR
    assert event.publication_eligible is False


def test_hdf_dvp_is_still_radar_in_engine_v1():
    event = HDFRadarAdapter.build_radar(make_evidence(stage="HDF_DVP"))
    assert event.event_class == MarketEventClass.RADAR
    assert event.publication_eligible is False
    assert event.objective_regions == ()
