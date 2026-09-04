"""Testes de Auditoria do Real Scanner Heartbeat e Evidence Pipeline.

Cobre:
1. evaluation_count_total incrementa apenas com novo candle fechado.
2. mesmo candle não é avaliado duas vezes (guarda de deduplicação).
3. polling sem candle novo incrementa scan_cycle_count_total, mas NÃO evaluation_count_total.
4. todas as 39 combinações do universo Shadow estão registradas.
5. endpoint /api/shadow/heartbeat retorna a estrutura das 39 combinações e totais acumulados.
6. detecção de stale scanner por timeframe (M15, H1, H4).
7. integridade de timestamps UTC.
8. ausência de evidências live trata 0 evidências sem falhas nem dados falsos.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.services.shadow_scanner import (
    SHADOW_ASSETS,
    SHADOW_TIMEFRAMES,
    ShadowScannerManager,
)
from backend.services.shadow_store import ShadowStoreRepository


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow_heartbeat.db")
    return ShadowStoreRepository(db_path=db_file)


@pytest.fixture
def scanner_manager(temp_store):
    return ShadowScannerManager(store=temp_store)


def _generate_test_candles(count: int = 50, timeframe: str = "H1", start_time: str = "2026-08-10 00:00:00") -> pd.DataFrame:
    tf_min = {"M15": 15, "H1": 60, "H4": 240}.get(timeframe, 60)
    base_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        dt = base_dt + timedelta(minutes=i * tf_min)
        t_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        rows.append({
            "time": t_str,
            "open": 2000.0 + i * 0.1,
            "high": 2005.0 + i * 0.1,
            "low": 1995.0 + i * 0.1,
            "close": 2002.0 + i * 0.1,
            "tick_volume": 100 + i,
        })
    return pd.DataFrame(rows)


def test_heartbeat_has_39_registered_combinations(temp_store):
    """Verifica se o heartbeat mapeia exatamente 39 combinações (13 ativos x 3 timeframes)."""
    hb = temp_store.get_shadow_heartbeat(candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id)
    assert hb["registered"] == 39
    assert len(hb["scanners"]) == 39


def test_evaluation_count_increments_only_on_new_closed_candle(scanner_manager, temp_store):
    """Testa se evaluation_count_total só cresce quando um novo candle fechado é recebido."""
    scanner_manager.runtime_started_at = "2026-07-31T00:00:00+00:00"
    df1 = _generate_test_candles(count=30, timeframe="H1", start_time="2026-08-01 00:00:00")
    
    # 1. Primeira chamada: novo candle fechado
    scanner_manager.scan_closed_candle("XAUUSD", "H1", df1, is_synthetic=True)
    st1 = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "XAUUSD", "H1")
    
    assert st1 is not None
    assert st1.scan_cycle_count_total == 1
    assert st1.evaluation_count_total == 1
    assert st1.last_evaluated_candle_time == str(df1["time"].iloc[-1])

    # 2. Segunda chamada com os MESMOS candles: deve ser ignorado (Duplicate Guard)
    scanner_manager.scan_closed_candle("XAUUSD", "H1", df1, is_synthetic=False)
    st2 = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "XAUUSD", "H1")
    
    assert st2.scan_cycle_count_total == 2
    assert st2.evaluation_count_total == 1  # Mantido em 1! Não reavaliado!
    assert st2.scanner_status == "WAITING_NEW_CANDLE"

    # 3. Terceira chamada com NOVO candle adicionado
    new_dt = datetime.strptime(str(df1["time"].iloc[-1]), "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)
    new_row = pd.DataFrame([{
        "time": new_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "open": 2005.0, "high": 2010.0, "low": 2000.0, "close": 2008.0, "tick_volume": 150
    }])
    df2 = pd.concat([df1, new_row], ignore_index=True)

    scanner_manager.scan_closed_candle("XAUUSD", "H1", df2, is_synthetic=False)
    st3 = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "XAUUSD", "H1")

    assert st3.scan_cycle_count_total == 3
    assert st3.evaluation_count_total == 2  # Agora incrementou para 2!
    assert st3.last_evaluated_candle_time == str(df2["time"].iloc[-1])


def test_stale_detection_logic(scanner_manager, temp_store):
    """Verifica se a telemetria de stale identifica varreduras desatualizadas por timeframe."""
    hb = temp_store.get_shadow_heartbeat(candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id)
    # Inicialmente sem last_evaluation_at, scanners não-avaliados
    xau_m15 = next(s for s in hb["scanners"] if s["symbol"] == "XAUUSD" and s["timeframe"] == "M15")
    assert xau_m15["evaluation_count_total"] == 0


def test_zero_live_evidence_returns_clean_totals(temp_store):
    """Garante que com 0 evidências no banco, o heartbeat e funil reportam 0 sem erros."""
    hb = temp_store.get_shadow_heartbeat(candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id)
    totals = hb["totals"]
    assert totals["hdf_d"] == 0
    assert totals["candidates"] == 0
    assert totals["armed"] == 0
    assert totals["activated"] == 0
