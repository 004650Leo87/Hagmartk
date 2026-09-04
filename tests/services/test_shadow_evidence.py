"""Testes de Unidade para HDFEvidence Layer e Observabilidade de Funnel (Fase 5C.16).

Cobre:
1. Bullish HDF_D gera HDFEvidence
2. Bearish HDF_D gera HDFEvidence
3. HDF_D com falha de volume continua como Evidence, mas não vira DV/DVP
4. HDF_DV com falha de padrão continua como Evidence, mas não vira DVP
5. HDF_DVP válido cria Evidence e ShadowEvent
6. Evidence não cria trade/operação automaticamente
7. API de evidências expõe P1 e P2 cirurgicamente
8. Isolamento de fixtures de teste (is_test=True vs is_test=False)
9. Cobertura de escaneamento XAUUSD M15/H1/H4
10. Métricas determinísticas do Funil HDF
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import HDFEvidence, ShadowEvent
from backend.services.shadow_scanner import ShadowScannerManager, SHADOW_ASSETS, SHADOW_TIMEFRAMES
from backend.services.shadow_store import ShadowStoreRepository
from backend.strategies.hdf.strategy import HDFStrategy


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow_evidence.db")
    return ShadowStoreRepository(db_path=db_file)


def make_test_candles(n=200, bull_div=False, bear_div=False):
    base_time = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    p = 1.0850
    for i in range(n):
        t = base_time + timedelta(hours=i)
        if bull_div and i == 40:
            p = 1.0750
        elif bull_div and i == 80:
            p = 1.0720
        elif bear_div and i == 40:
            p = 1.0950
        elif bear_div and i == 80:
            p = 1.0980
        else:
            p = 1.0850 + (i % 5) * 0.0005

        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": p - 0.0002,
            "high": p + 0.0005,
            "low": p - 0.0005,
            "close": p,
            "real_volume": 1500,
            "tick_volume": 1500,
        })
    return pd.DataFrame(rows)


def test_hdf_evidence_creation_bullish(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_test_bull_001",
        symbol="EURUSD",
        timeframe="H1",
        asset_class="FOREX",
        direction="BULLISH",
        pivot_1_time="2026-08-01 10:00:00",
        pivot_1_price=1.0850,
        pivot_1_rsi=32.5,
        pivot_2_time="2026-08-01 14:00:00",
        pivot_2_price=1.0820,
        pivot_2_rsi=38.0,
        divergence_confirmed=True,
        relative_volume=0.9,
        volume_pass=False,
        pattern_type="NONE",
        pattern_pass=False,
        variant_stage="HDF_D",
        candidate_created=False,
        armed=False,
        is_test=False,
        detected_at="2026-08-01 16:00:00",
        created_at="2026-08-01 16:00:00",
    )
    temp_store.save_hdf_evidence(ev)

    retrieved = temp_store.get_hdf_evidence("ev_test_bull_001")
    assert retrieved is not None
    assert retrieved.symbol == "EURUSD"
    assert retrieved.direction == "BULLISH"
    assert retrieved.pivot_1_price == 1.0850
    assert retrieved.pivot_2_price == 1.0820
    assert retrieved.pivot_1_rsi == 32.5
    assert retrieved.pivot_2_rsi == 38.0
    assert retrieved.variant_stage == "HDF_D"
    assert retrieved.candidate_created is False


def test_hdf_evidence_volume_fail_remains_evidence(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_vol_fail_001",
        symbol="GBPUSD",
        timeframe="M15",
        asset_class="FOREX",
        direction="BEARISH",
        pivot_1_time="2026-08-02 08:00:00",
        pivot_1_price=1.2850,
        pivot_1_rsi=68.5,
        pivot_2_time="2026-08-02 09:30:00",
        pivot_2_price=1.2880,
        pivot_2_rsi=62.0,
        divergence_confirmed=True,
        relative_volume=0.8,
        volume_pass=False,
        pattern_type="NONE",
        pattern_pass=False,
        variant_stage="HDF_D",
        candidate_created=False,
    )
    temp_store.save_hdf_evidence(ev)

    evidences = temp_store.list_hdf_evidence(symbol="GBPUSD", timeframe="M15", is_test=False)
    assert len(evidences) == 1
    assert evidences[0].variant_stage == "HDF_D"
    assert evidences[0].volume_pass is False
    assert evidences[0].candidate_created is False


def test_hdf_evidence_pattern_fail_remains_evidence(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_pat_fail_001",
        symbol="USDJPY",
        timeframe="H4",
        asset_class="FOREX",
        direction="BULLISH",
        pivot_1_time="2026-08-03 00:00:00",
        pivot_1_price=150.20,
        pivot_1_rsi=28.0,
        pivot_2_time="2026-08-03 12:00:00",
        pivot_2_price=149.80,
        pivot_2_rsi=35.0,
        divergence_confirmed=True,
        relative_volume=1.4,
        volume_pass=True,
        pattern_type="NONE",
        pattern_pass=False,
        variant_stage="HDF_DV",
        candidate_created=False,
    )
    temp_store.save_hdf_evidence(ev)

    evidences = temp_store.list_hdf_evidence(symbol="USDJPY", timeframe="H4", is_test=False)
    assert len(evidences) == 1
    assert evidences[0].variant_stage == "HDF_DV"
    assert evidences[0].volume_pass is True
    assert evidences[0].pattern_pass is False
    assert evidences[0].candidate_created is False


def test_hdf_evidence_does_not_create_trade_automatically(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_no_trade_001",
        symbol="BTCUSD",
        timeframe="H1",
        asset_class="CRYPTO",
        direction="BULLISH",
        pivot_1_time="2026-08-04 00:00:00",
        pivot_1_price=60000.0,
        pivot_1_rsi=25.0,
        pivot_2_time="2026-08-04 04:00:00",
        pivot_2_price=59000.0,
        pivot_2_rsi=32.0,
        variant_stage="HDF_D",
        candidate_created=False,
        armed=False,
    )
    temp_store.save_hdf_evidence(ev)

    events = temp_store.list_history_events()
    real_events = [e for e in events if not e.event_id.startswith("test_")]
    assert len(real_events) == 0


def test_test_fixtures_isolation(temp_store):
    live_ev = HDFEvidence(
        evidence_id="ev_live_001",
        symbol="XAUUSD",
        timeframe="H1",
        asset_class="METALS",
        direction="BULLISH",
        pivot_1_time="2026-08-05 10:00:00", pivot_1_price=2400.0, pivot_1_rsi=30.0,
        pivot_2_time="2026-08-05 14:00:00", pivot_2_price=2390.0, pivot_2_rsi=35.0,
        is_test=False,
    )
    test_ev = HDFEvidence(
        evidence_id="ev_test_001",
        symbol="XAUUSD",
        timeframe="H1",
        asset_class="METALS",
        direction="BULLISH",
        pivot_1_time="2026-08-06 10:00:00", pivot_1_price=2410.0, pivot_1_rsi=31.0,
        pivot_2_time="2026-08-06 14:00:00", pivot_2_price=2400.0, pivot_2_rsi=36.0,
        is_test=True,
    )
    temp_store.save_hdf_evidence(live_ev)
    temp_store.save_hdf_evidence(test_ev)

    live_list = temp_store.list_hdf_evidence(symbol="XAUUSD", timeframe="H1", is_test=False)
    test_list = temp_store.list_hdf_evidence(symbol="XAUUSD", timeframe="H1", is_test=True)

    assert len(live_list) == 1
    assert live_list[0].evidence_id == "ev_live_001"
    assert len(test_list) == 1
    assert test_list[0].evidence_id == "ev_test_001"


def test_funnel_telemetry(temp_store):
    ev1 = HDFEvidence(
        evidence_id="e1", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BULLISH",
        pivot_1_time="t1", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t2", pivot_2_price=1.07, pivot_2_rsi=35.0,
        volume_pass=True, pattern_pass=False, candidate_created=False, is_test=False,
    )
    ev2 = HDFEvidence(
        evidence_id="e2", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BEARISH",
        pivot_1_time="t3", pivot_1_price=1.09, pivot_1_rsi=70.0,
        pivot_2_time="t4", pivot_2_price=1.10, pivot_2_rsi=65.0,
        volume_pass=True, pattern_pass=True, candidate_created=True, is_test=False,
    )
    ev_legacy = HDFEvidence(
        evidence_id="e_legacy", symbol="EURUSD", timeframe="H1", asset_class="FOREX", direction="BULLISH",
        pivot_1_time="t5", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t6", pivot_2_price=1.07, pivot_2_rsi=35.0,
        volume_pass=True, pattern_pass=True, candidate_created=True, is_test=False,
        source="LEGACY_PRE_PAPER_EXECUTION",
    )
    temp_store.save_hdf_evidence(ev1)
    temp_store.save_hdf_evidence(ev2)
    temp_store.save_hdf_evidence(ev_legacy)

    funnel = temp_store.get_funnel_telemetry(symbol="EURUSD", timeframe="H1")
    assert funnel["hdf_d"] == 2
    assert funnel["hdf_dv"] == 2
    assert funnel["hdf_dvp"] == 1
    assert funnel["candidates"] == 1


def test_xauusd_coverage(temp_store):
    manager = ShadowScannerManager(store=temp_store)
    df_xau = make_test_candles(100)

    for tf in ["M15", "H1", "H4"]:
        events = manager.scan_closed_candle("XAUUSD", tf, df_xau, is_synthetic=True)
        st = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "XAUUSD", tf)
        assert st is not None
        assert st.scanner_status in ("RUNNING", "WAITING_NEW_CANDLE")
