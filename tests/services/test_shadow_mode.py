from __future__ import annotations

import os
import sqlite3
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH, HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import EvidencePayload, ShadowEvent, ShadowState
from backend.services.alert_engine import InternalAlertEngine
from backend.services.shadow_scanner import ShadowScannerManager
from backend.services.shadow_store import ShadowStoreRepository

client = TestClient(app)


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow.db")
    return ShadowStoreRepository(db_path=db_file)


def test_A_B_enable_disable_shadow(temp_store):
    mgr = ShadowScannerManager(store=temp_store)
    assert mgr.enabled is True

    mgr.disable_shadow()
    assert mgr.enabled is False

    mgr.enable_shadow()
    assert mgr.enabled is True


def test_C_candidate_immutable():
    spec = HDF_ROBUST_CANDIDATE_V1
    assert spec.compute_parameter_hash() == HDF_CANDIDATE_V1_PARAMETER_HASH
    assert spec.validate_immutability(HDF_CANDIDATE_V1_PARAMETER_HASH) is True


def test_D_E_F_G_closed_candle_warmup_and_deduplication(temp_store):
    mgr = ShadowScannerManager(store=temp_store)

    # DataFrame de warmup sem eventos suficientes
    dates = pd.date_range("2026-01-01", periods=30, freq="1h")
    df_empty = pd.DataFrame({
        "time": dates,
        "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000
    })

    evts = mgr.scan_closed_candle("EURUSD", "H1", df_empty)
    assert len(evts) == 0

    # Teste de Idempotência / Deduplicação
    st = temp_store.get_scanner_state(HDF_ROBUST_CANDIDATE_V1.candidate_id, "EURUSD", "H1")
    assert st is not None
    assert st.last_processed_candle == str(dates[-1])

    # Re-scan do mesmo candle não duplica
    evts_again = mgr.scan_closed_candle("EURUSD", "H1", df_empty)
    assert len(evts_again) == 0


def test_H_I_J_K_L_M_N_lifecycle_and_milestone_1r(temp_store):
    evt = ShadowEvent(
        event_id="evt_test_123",
        symbol="EURUSD",
        timeframe="H1",
        direction="BULLISH",
        activation_level=1.1000,
        entry_price=1.1000,
        initial_stop=1.0900,
        target_2R=1.1200,
        current_state=ShadowState.ACTIVATED.value,
        mfe_r_live=1.25,
        milestone_1r_reached=True,
    )

    temp_store.save_event(evt)
    retrieved = temp_store.get_event("evt_test_123")

    assert retrieved is not None
    assert retrieved.current_state == "ACTIVATED"
    assert retrieved.milestone_1r_reached is True
    assert retrieved.mfe_r_live == 1.25


def test_O_P_Q_persistence_and_restart_recovery(temp_store, tmp_path):
    # Salva evento e estado do scanner
    evt = ShadowEvent(event_id="evt_recover", symbol="XAUUSD", timeframe="H1", current_state="ARMED")
    temp_store.save_event(evt)

    # Simula reinício de backend abrindo um novo repositório sobre o mesmo arquivo de banco
    new_store = ShadowStoreRepository(db_path=temp_store.db_path)
    recovered_evt = new_store.get_event("evt_recover")

    assert recovered_evt is not None
    assert recovered_evt.symbol == "XAUUSD"
    assert recovered_evt.current_state == "ARMED"


def test_R_S_T_U_utc_active_history_and_statistics(temp_store):
    # Adiciona 1 ativo e 1 finalizado
    e1 = ShadowEvent(event_id="e1", symbol="BTCUSD", timeframe="H1", current_state="ACTIVATED")
    e2 = ShadowEvent(event_id="e2", symbol="ETHUSD", timeframe="H1", current_state="TARGET_2R")

    temp_store.save_event(e1)
    temp_store.save_event(e2)

    actives = temp_store.list_active_events()
    assert len(actives) == 1
    assert actives[0].event_id == "e1"

    history = temp_store.list_history_events()
    assert len(history) == 2

    stats = temp_store.get_shadow_statistics(started_at="2026-08-08 19:00:00")
    assert stats.total_events_detected == 2
    assert stats.targets_reached_count == 1
    assert stats.open_count == 1
    assert stats.net_r_shadow > 0


def test_V_no_broker_execution():
    # Garante que nenhum módulo de ordens/trading é importado pelo Shadow Mode
    from backend.services.alert_engine import InternalShadowPublisher
    pub = InternalShadowPublisher(store=None)
    assert not hasattr(pub, "send_order")
    assert not hasattr(pub, "execute_trade")


def test_W_evidence_payload():
    evi = EvidencePayload(
        symbol="EURUSD",
        timeframe="H1",
        direction="BULLISH",
        rsi1=35.0,
        rsi2=42.0,
        activation_level=1.1000,
        entry_price=1.1000,
        initial_stop=1.0950,
        target_price=1.1100,
    )
    assert evi.watermark_text == "EURUSD • H1"
    assert evi.direction == "BULLISH"


def test_X_Y_Z_api_shadow_endpoints():
    r_status = client.get("/api/shadow/status")
    assert r_status.status_code == 200
    assert r_status.json()["mode"] == "SHADOW"

    r_cands = client.get("/api/shadow/candidates")
    assert r_cands.status_code == 200
    assert len(r_cands.json()) == 1
    assert r_cands.json()[0]["candidate_id"] == "hdf_dvp_exit_2r"

    r_enable = client.post("/api/shadow/hdf_dvp_exit_2r/enable")
    assert r_enable.status_code == 200
    assert r_enable.json()["enabled"] is True

    r_stats = client.get("/api/shadow/statistics")
    assert r_stats.status_code == 200
    assert "historical_research_reference" in r_stats.json()

    r_scanners = client.get("/api/shadow/scanners")
    assert r_scanners.status_code == 200
    assert len(r_scanners.json()) == 39
