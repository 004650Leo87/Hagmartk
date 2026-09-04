from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import ShadowEvent, ShadowState
from backend.services.shadow_scanner import ShadowScannerManager
from backend.services.shadow_store import ShadowStoreRepository
from backend.strategies.hdf.models import (
    HDFOccurrence,
    HDFState,
    HDFTemporalModel,
    ReversalPatternType,
)


@pytest.fixture
def temp_store(tmp_path):
    return ShadowStoreRepository(str(tmp_path / "recovery.db"))


def _candles() -> pd.DataFrame:
    start = datetime(2026, 9, 4, 3, 0, tzinfo=timezone.utc)
    rows = []
    for i in range(32):
        t = start + timedelta(minutes=15 * i)
        rows.append({
            "time": t.isoformat(), "open": 1.1000, "high": 1.1020,
            "low": 1.0980, "close": 1.1010, "tick_volume": 1200,
        })
    return pd.DataFrame(rows)


def _occurrence(state: HDFState = HDFState.ACTIVATED) -> HDFOccurrence:
    temporal = HDFTemporalModel(
        pivot_1_time="2026-09-04T08:00:00+00:00",
        pivot_2_time="2026-09-04T09:45:00+00:00",
        pivot_1_confirmed_at="2026-09-04T08:30:00+00:00",
        pivot_2_confirmed_at="2026-09-04T10:15:00+00:00",
        divergence_confirmed_at="2026-09-04T10:15:00+00:00",
        volume_observed_at="2026-09-04T10:15:00+00:00",
        reversal_pattern_time="2026-09-04T10:15:00+00:00",
        confluence_completed_at="2026-09-04T10:15:00+00:00",
        armed_at="2026-09-04T10:15:00+00:00",
        activation_time="2026-09-04T10:30:00+00:00",
        entry_at="2026-09-04T10:30:00+00:00",
        data_available_at_decision="2026-09-04T10:15:00+00:00",
    )
    return HDFOccurrence(
        occurrence_id="occ_real_model", symbol="EURUSD", timeframe="M15",
        direction="BULLISH", state=state, temporal_model=temporal, variant="HDF_DVP",
        price_p1=1.1010, price_p2=1.0990, rsi_p1=30.0, rsi_p2=34.0,
        relative_volume=1.2, pattern_type=ReversalPatternType.BULLISH_ENGULFING,
        pattern_high=1.1000, pattern_low=1.0900,
        activation_level=1.1000, entry_price=1.1010,
        initial_stop=1.0900, initial_risk=0.0110,
        metadata={"activation_bar_index": 30},
    )


def _manager(temp_store: ShadowStoreRepository) -> ShadowScannerManager:
    cid = HDF_ROBUST_CANDIDATE_V1.candidate_id
    temp_store.save_shadow_session(cid, "2026-09-04T01:40:49+00:00", True)
    temp_store.save_evidence_session(cid, "2026-09-04T10:00:00+00:00")
    manager = ShadowScannerManager(store=temp_store)
    manager.runtime_started_at = "2026-09-04T10:20:00+00:00"
    return manager


def _isolate_analysis(monkeypatch, manager, occ):
    monkeypatch.setattr(
        manager.strategy, "evaluate_full_dataset_analysis",
        lambda df, symbol, timeframe, **kwargs: {"occurrences": [occ]},
    )
    monkeypatch.setattr(manager, "_process_hdf_evidences", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "backend.services.fibonacci_prospective_telemetry.FibonacciProspectiveTelemetryEngine.process_occurrences",
        lambda *args, **kwargs: 0,
    )


def test_runtime_cutoff_rejects_new_recovery_backfill(temp_store, monkeypatch):
    manager = _manager(temp_store)
    occ = _occurrence()
    _isolate_analysis(monkeypatch, manager, occ)
    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)

    assert events == []
    assert temp_store.get_event("evt_EURUSD_M15_1788516900") is None


def test_existing_event_can_continue_after_restart(temp_store, monkeypatch):
    manager = _manager(temp_store)
    occ = _occurrence()
    _isolate_analysis(monkeypatch, manager, occ)

    existing = ShadowEvent(
        event_id="evt_EURUSD_M15_1788516900",
        symbol="EURUSD", timeframe="M15", direction="BULLISH",
        confluence_time="2026-09-04T10:15:00+00:00",
        armed_at="2026-09-04T10:15:00+00:00",
        activation_level=1.1000, initial_stop=1.0900,
        current_state=ShadowState.ARMED.value,
        created_at="2026-09-04T10:16:00+00:00",
        updated_at="2026-09-04T10:16:00+00:00",
    )
    assert temp_store.save_event(existing) is True

    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)
    assert events == []
    saved = temp_store.get_event(existing.event_id)
    assert saved is not None
    assert saved.current_state == ShadowState.ACTIVATED.value
    assert saved.activated_at == "2026-09-04T10:30:00+00:00"
    assert saved.entry_price == pytest.approx(1.1000)
    assert saved.initial_risk == pytest.approx(0.0100)


def test_real_hdf_occurrence_maps_to_shadow_event_without_legacy_nested_fields(temp_store, monkeypatch):
    manager = _manager(temp_store)
    manager.runtime_started_at = "2026-09-04T10:00:00+00:00"
    occ = _occurrence()
    _isolate_analysis(monkeypatch, manager, occ)
    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)
    assert len(events) == 1
    evt = events[0]

    assert evt.direction == "BULLISH"
    assert evt.pattern_type == "BULLISH_ENGULFING"
    assert evt.pivot_1_time == "2026-09-04T08:00:00+00:00"
    assert evt.pivot_2_time == "2026-09-04T09:45:00+00:00"
    assert evt.divergence_confirmed_at == "2026-09-04T10:15:00+00:00"
    assert evt.confluence_time == "2026-09-04T10:15:00+00:00"
    assert evt.activated_at == "2026-09-04T10:30:00+00:00"
    assert evt.entry_price == pytest.approx(1.1010)
    assert evt.initial_risk == pytest.approx(0.0110)
    assert evt.target_2R == pytest.approx(1.1230)
    assert evt.current_state == ShadowState.ACTIVATED.value


def test_hdf_evidence_runtime_cutoff_is_stricter_than_feature_t0(temp_store):
    manager = _manager(temp_store)

    assert manager._should_persist_hdf_evidence(
        "2026-09-04T10:15:00+00:00", False
    ) is False
    assert manager._should_persist_hdf_evidence(
        "2026-09-04T10:20:00+00:00", False
    ) is True
    assert manager._should_persist_hdf_evidence("old", True) is True


@pytest.mark.parametrize(
    ("hdf_state", "shadow_state"),
    [
        (HDFState.TARGET_2, ShadowState.TARGET_2R.value),
        (HDFState.STOPPED, ShadowState.STOPPED.value),
    ],
)
def test_canonical_terminal_hdf_states_map_to_shadow_states(
    temp_store, monkeypatch, hdf_state, shadow_state
):
    manager = _manager(temp_store)
    manager.runtime_started_at = "2026-09-04T10:00:00+00:00"
    occ = _occurrence(state=hdf_state)
    _isolate_analysis(monkeypatch, manager, occ)

    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)
    assert len(events) == 1
    assert events[0].current_state == shadow_state


def test_invalid_decision_timestamp_fails_closed(temp_store, monkeypatch):
    manager = _manager(temp_store)
    occ = _occurrence()
    occ.temporal_model.confluence_completed_at = "not-a-time"
    _isolate_analysis(monkeypatch, manager, occ)

    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)
    assert events == []


def test_runtime_baseline_skips_pre_start_candle_without_telemetry_or_analysis(temp_store, monkeypatch):
    manager = _manager(temp_store)
    manager.runtime_started_at = "2026-09-04T11:00:00+00:00"
    monkeypatch.setattr(
        manager.strategy,
        "evaluate_full_dataset_analysis",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("baseline must not analyze")),
    )

    events = manager.scan_closed_candle("EURUSD", "M15", _candles(), is_synthetic=False)
    assert events == []
    state = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "EURUSD", "M15")
    assert state is not None
    assert state.last_processed_candle == "2026-09-04T10:45:00+00:00"
    assert state.evaluation_count_total == 0
    with temp_store._get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM shadow_scanner_telemetry").fetchone()[0]
    assert count == 0