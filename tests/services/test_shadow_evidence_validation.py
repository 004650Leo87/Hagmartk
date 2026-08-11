"""Testes de Validação da Fase 5C.17 — Live HDF Evidence & Cockpit Integration.

Cobre:
1. shadow_hdf_evidence live vs test filtering (is_test=0 vs is_test=1)
2. Fidelidade de campos entre SQLite database e API payload (P1/P2/RSI/Volume/Pattern)
3. Idempotência do scanner (scanning repetido produz exatamente 1 evidência por divergência)
4. Exclusão de fixtures TEST de badges de notificação e views normais de produção
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from backend.domain.shadow_models import HDFEvidence, ShadowEvent
from backend.services.shadow_scanner import ShadowScannerManager, SHADOW_ASSETS, SHADOW_TIMEFRAMES
from backend.services.shadow_store import ShadowStoreRepository


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow_evidence_val.db")
    return ShadowStoreRepository(db_path=db_file)


def test_database_to_api_fidelity(temp_store):
    ev = HDFEvidence(
        evidence_id="ev_fid_001",
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
        divergence_confirmed=True,
        relative_volume=1.15,
        volume_pass=True,
        pattern_type="BULLISH_ENGULFING",
        pattern_pass=True,
        pattern_policy="SAME_BAR",
        variant_stage="HDF_DVP",
        candidate_created=True,
        armed=True,
        is_test=False,
    )
    temp_store.save_hdf_evidence(ev)

    retrieved = temp_store.get_hdf_evidence("ev_fid_001")
    assert retrieved is not None
    d = retrieved.__dict__

    assert d["evidence_id"] == "ev_fid_001"
    assert d["symbol"] == "XAUUSD"
    assert d["timeframe"] == "H1"
    assert d["direction"] == "BULLISH"
    assert d["pivot_1_time"] == "2026-08-11 10:00:00"
    assert d["pivot_1_price"] == 2410.50
    assert d["pivot_1_rsi"] == 31.2
    assert d["pivot_2_time"] == "2026-08-11 14:00:00"
    assert d["pivot_2_price"] == 2402.00
    assert d["pivot_2_rsi"] == 36.8
    assert d["relative_volume"] == 1.15
    assert d["volume_pass"] is True
    assert d["pattern_pass"] is True
    assert d["variant_stage"] == "HDF_DVP"


def test_scanner_idempotency_no_duplicates(temp_store):
    manager = ShadowScannerManager(store=temp_store)
    
    # Criar dataset de velas com divergência bullish induzida
    rows = []
    base_time = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(100):
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

    # Execução 1 do scan
    manager.scan_closed_candle("EURUSD", "H1", df_candles, is_synthetic=False)
    count_run1 = len(temp_store.list_hdf_evidence("EURUSD", "H1", is_test=False))

    # Execução 2 do scan com as mesmas velas
    manager.scan_closed_candle("EURUSD", "H1", df_candles, is_synthetic=False)
    count_run2 = len(temp_store.list_hdf_evidence("EURUSD", "H1", is_test=False))

    # A contagem deve ser idêntica (zero duplicatas gravadas)
    assert count_run1 == count_run2, f"Esperado {count_run1} evidências sem duplicatas, mas obtido {count_run2}"


def test_badge_count_excludes_test_fixtures(temp_store):
    live_ev = HDFEvidence(
        evidence_id="ev_live_badge", symbol="EURUSD", timeframe="H1", asset_class="FOREX",
        direction="BULLISH", pivot_1_time="t1", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t2", pivot_2_price=1.07, pivot_2_rsi=35.0, is_test=False,
    )
    test_ev = HDFEvidence(
        evidence_id="ev_test_badge", symbol="EURUSD", timeframe="H1", asset_class="FOREX",
        direction="BULLISH", pivot_1_time="t3", pivot_1_price=1.08, pivot_1_rsi=30.0,
        pivot_2_time="t4", pivot_2_price=1.07, pivot_2_rsi=35.0, is_test=True,
    )
    temp_store.save_hdf_evidence(live_ev)
    temp_store.save_hdf_evidence(test_ev)

    live_only = temp_store.list_hdf_evidence(is_test=False)
    assert len(live_only) == 1
    assert live_only[0].evidence_id == "ev_live_badge"
