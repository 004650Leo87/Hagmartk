"""Testes da Fase 5C.18 — Clean Evidence Store, Provenance & Scanner Telemetry.

Cobre:
1. shadow_hdf_evidence limpo sem contaminação sintética
2. Proveniência obrigatória (source: LIVE_PROSPECTIVE, HISTORICAL_BACKFILL, TEST, DEMO)
3. API live-only por padrão (retorna apenas source=LIVE_PROSPECTIVE)
4. Exclusão de evidências TEST/BACKFILL das visualizações normais de produção
5. Validação de integridade de preço (PRICE_INTEGRITY_FAIL se preços forem inválidos/nulos)
6. Idempotência por combinação única de pivôs (UNIQUE(symbol, timeframe, pivot_2_time, direction))
7. Telemetria de cobertura de scanners (registered, active, recently_scanned, stale, errors)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import HDFEvidence, ShadowScannerState
from backend.services.shadow_scanner import ShadowScannerManager, SHADOW_ASSETS, SHADOW_TIMEFRAMES
from backend.services.shadow_store import ShadowStoreRepository


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow_clean_evidence.db")
    return ShadowStoreRepository(db_path=db_file)


def test_provenance_column_defaults_to_live_prospective(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_clean_001",
        symbol="XAUUSD",
        timeframe="H1",
        asset_class="METALS",
        direction="BULLISH",
        pivot_1_time="2026-08-11 10:00:00",
        pivot_1_price=2410.50,
        pivot_1_rsi=31.2,
        pivot_2_time="2026-08-11 14:00:00",
        pivot_2_price=2402.00,
        pivot_2_rsi=36.8,
        source="LIVE_PROSPECTIVE",
        is_test=False,
    )
    temp_store.save_hdf_evidence(ev)

    retrieved = temp_store.get_hdf_evidence("ev_clean_001")
    assert retrieved is not None
    assert retrieved.source == "LIVE_PROSPECTIVE"
    assert retrieved.is_test is False


def test_list_hdf_evidence_filters_by_source(temp_store):
    live_ev = HDFEvidence(
        evidence_id="ev_live_001", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BULLISH",
        pivot_1_time="t1", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t2", pivot_2_price=1.07, pivot_2_rsi=35.0,
        source="LIVE_PROSPECTIVE", is_test=False,
    )
    test_ev = HDFEvidence(
        evidence_id="ev_test_001", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BULLISH",
        pivot_1_time="t3", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t4", pivot_2_price=1.07, pivot_2_rsi=35.0,
        source="TEST", is_test=True,
    )
    backfill_ev = HDFEvidence(
        evidence_id="ev_bf_001", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BEARISH",
        pivot_1_time="t5", pivot_1_price=1.09, pivot_1_rsi=70.0,
        pivot_2_time="t6", pivot_2_price=1.10, pivot_2_rsi=65.0,
        source="HISTORICAL_BACKFILL", is_test=False,
    )

    temp_store.save_hdf_evidence(live_ev)
    temp_store.save_hdf_evidence(test_ev)
    temp_store.save_hdf_evidence(backfill_ev)

    live_list = temp_store.list_hdf_evidence(symbol="EURUSD", timeframe="H1", source="LIVE_PROSPECTIVE")
    assert len(live_list) == 1
    assert live_list[0].evidence_id == "ev_live_001"
    assert live_list[0].source == "LIVE_PROSPECTIVE"


def test_price_integrity_validation_fails_on_zero_price(temp_store):
    manager = ShadowScannerManager(store=temp_store)
    
    rows = []
    base_time = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(50):
        t = base_time + timedelta(hours=i)
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0,
            "real_volume": 100, "tick_volume": 100,
        })
    df_zero = pd.DataFrame(rows)

    manager.scan_closed_candle("EURUSD", "H1", df_zero, is_synthetic=True)
    live_evs = temp_store.list_hdf_evidence(symbol="EURUSD", timeframe="H1", source="LIVE_PROSPECTIVE")
    assert len(live_evs) == 0


def test_scanner_idempotency_unique_constraint(temp_store):
    manager = ShadowScannerManager(store=temp_store)
    rows = []
    base_time = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(80):
        t = base_time + timedelta(hours=i)
        p = 1.0850 + (i % 5) * 0.0005
        if i == 20: p = 1.0750
        if i == 45: p = 1.0720
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": p - 0.0002, "high": p + 0.0005, "low": p - 0.0005, "close": p,
            "real_volume": 1200, "tick_volume": 1200,
        })
    df_candles = pd.DataFrame(rows)

    manager.scan_closed_candle("EURUSD", "H1", df_candles, is_synthetic=True)
    count1 = len(temp_store.list_hdf_evidence(include_non_live=True))

    manager.scan_closed_candle("EURUSD", "H1", df_candles, is_synthetic=True)
    count2 = len(temp_store.list_hdf_evidence(include_non_live=True))

    assert count1 == count2, "Zero duplicatas devem ser inseridas"


def test_xauusd_scanner_state_telemetry(temp_store):
    cid = HDF_ROBUST_CANDIDATE_V1.candidate_id
    for tf in ["M15", "H1", "H4"]:
        st_obj = ShadowScannerState(
            candidate_id=cid, symbol="XAUUSD", timeframe=tf,
            enabled=True, last_processed_candle="2026-08-11 14:00:00",
            last_scan_at="2026-08-11 14:00:00", scanner_status="RUNNING"
        )
        temp_store.save_scanner_state(st_obj)
        st_updated = temp_store.get_scanner_state(cid, "XAUUSD", tf)
        assert st_updated is not None
        assert st_updated.scanner_status == "RUNNING"


def test_hdf_decision_snapshot_is_immutable_on_rescan(temp_store):
    first = HDFEvidence(
        evidence_id="ev_immutable_first", symbol="USDCHF", timeframe="M15", asset_class="FOREX",
        direction="BEARISH", pivot_1_time="t1", pivot_1_price=0.8080, pivot_1_rsi=60.0,
        pivot_2_time="t2", pivot_2_price=0.8081, pivot_2_rsi=55.0,
        relative_volume=1.6, volume_pass=True, pattern_type="BEARISH_ENGULFING",
        pattern_pass=True, variant_stage="HDF_DVP", candidate_created=True, armed=True,
        source="LIVE_PROSPECTIVE", is_test=False, detected_at="2026-09-04T01:45:00+00:00",
    )
    later = HDFEvidence(
        evidence_id="ev_immutable_later", symbol="USDCHF", timeframe="M15", asset_class="FOREX",
        direction="BEARISH", pivot_1_time="t1b", pivot_1_price=0.8080, pivot_1_rsi=59.0,
        pivot_2_time="t2", pivot_2_price=0.8081, pivot_2_rsi=54.0,
        relative_volume=0.7, volume_pass=False, pattern_type="NONE",
        pattern_pass=False, variant_stage="HDF_D", candidate_created=False, armed=False,
        source="LIVE_PROSPECTIVE", is_test=False, detected_at="2026-09-04T02:00:00+00:00",
    )
    temp_store.save_hdf_evidence(first)
    temp_store.save_hdf_evidence(later)

    saved = temp_store.get_hdf_evidence("ev_immutable_first")
    assert saved is not None
    assert saved.variant_stage == "HDF_DVP"
    assert saved.relative_volume == 1.6
    assert saved.pattern_pass is True
    assert saved.candidate_created is True
    assert temp_store.get_hdf_evidence("ev_immutable_later") is None


def test_hdf_evidence_t0_can_be_stricter_than_shadow_t0(temp_store):
    candidate_id = HDF_ROBUST_CANDIDATE_V1.candidate_id
    temp_store.save_shadow_session(
        candidate_id, "2026-09-04T01:40:49+00:00", True
    )
    temp_store.save_evidence_session(
        candidate_id, "2026-09-04T09:50:00+00:00"
    )
    manager = ShadowScannerManager(store=temp_store)
    manager.runtime_started_at = "2026-09-04T09:40:00+00:00"

    assert manager.shadow_started_at == "2026-09-04T01:40:49+00:00"
    assert manager.evidence_started_at == "2026-09-04T09:50:00+00:00"
    assert manager._should_persist_hdf_evidence(
        "2026-09-04T09:49:59+00:00", False
    ) is False
    assert manager._should_persist_hdf_evidence(
        "2026-09-04T09:50:00+00:00", False
    ) is True
    assert manager._should_persist_hdf_evidence("old", True) is True
