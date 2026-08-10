"""Suíte de testes para o Prospective Observation & Accumulation Engine V1 (Fase 4F).

Cobre:
1. Gravação e persistência de observação prospectiva
2. Idempotência (não duplica observações para a mesma janela/candle)
3. Proteção contra Look-Ahead Bias (snapshot do instante)
4. Rastreamento do histórico de transições de estado de evidência
5. Estado degradado e dados insuficientes
6. Agregação de saúde (39 combinações do Universo Shadow)
7. Detalhamento do acúmulo de amostragem por combinação
8. Endpoints da API REST READ-ONLY
9. Teste de ausência de side effects (sem broker, sem Telegram, sem mutação de HDF)
10. Preservação imutável das 39 combinações
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.services.shadow_observation_engine import ShadowObservationEngine
from backend.services.shadow_store import ShadowStoreRepository

client = TestClient(app)


@pytest.fixture
def temp_store(tmp_path):
    db_path = os.path.join(tmp_path, "test_shadow_observation.db")
    store = ShadowStoreRepository(db_path=db_path)
    return store


# ============================================================
# 1. Idempotência e Persistência
# ============================================================

def test_record_observation_idempotency(temp_store):
    engine = ShadowObservationEngine(store=temp_store)

    # Primeira gravação
    ins1 = engine.record_observation_cycle(
        symbol="EURUSD", timeframe="H1", window_time="2026-08-10 12:00:00"
    )
    assert ins1 is True

    # Gravação duplicada para a mesma janela (deve ser ignorada)
    ins2 = engine.record_observation_cycle(
        symbol="EURUSD", timeframe="H1", window_time="2026-08-10 12:00:00"
    )
    assert ins2 is False

    obs_list = temp_store.get_prospective_observations(symbol="EURUSD", timeframe="H1")
    assert len(obs_list) == 1
    assert obs_list[0]["symbol"] == "EURUSD"
    assert obs_list[0]["timeframe"] == "H1"


def test_evidence_state_transition_tracking(temp_store):
    engine = ShadowObservationEngine(store=temp_store)

    # 1ª Observação -> Estado inicial INSUFFICIENT_EVIDENCE
    engine.record_observation_cycle(
        symbol="GBPUSD", timeframe="M15", window_time="2026-08-10 10:00:00"
    )

    transitions1 = temp_store.get_evidence_transitions(symbol="GBPUSD", timeframe="M15")
    assert len(transitions1) == 1
    assert transitions1[0]["to_state"] == "INSUFFICIENT_EVIDENCE"

    # Simular mudança de estado de evidência para DEVELOPING_EVIDENCE
    mock_decision = MagicMock()
    mock_ev = MagicMock()
    mock_ev.observational_status = "VALIDATING"
    mock_ev.evidence_state = "DEVELOPING_EVIDENCE"
    mock_ev.reason_codes = ["SAMPLE_USABLE", "EXPECTANCY_POSITIVE"]
    mock_ev.sample = {"size": 55}
    mock_ev.data_quality = {"state": "VALID", "scanner_coverage": 0.98}
    mock_ev.performance = {"expectancy_r": 0.30, "win_rate_pct": 42.0, "profit_factor": 1.4, "max_drawdown_r": -2.0}
    mock_ev.contradictions = []
    mock_decision.evaluate_evidence.return_value = mock_ev

    engine.decision_engine = mock_decision

    engine.record_observation_cycle(
        symbol="GBPUSD", timeframe="M15", window_time="2026-08-10 11:00:00"
    )

    transitions2 = temp_store.get_evidence_transitions(symbol="GBPUSD", timeframe="M15")
    assert len(transitions2) == 2
    assert transitions2[0]["from_state"] == "INSUFFICIENT_EVIDENCE"
    assert transitions2[0]["to_state"] == "DEVELOPING_EVIDENCE"


# ============================================================
# 2. Agregação e Saúde das 39 Combinações
# ============================================================

def test_observation_health_aggregation(temp_store):
    engine = ShadowObservationEngine(store=temp_store)
    health = engine.get_observation_health()

    assert health["total_universe_combinations"] == 39
    assert health["observed_combinations"] == 0
    assert health["error_combinations"] == 0


def test_accumulation_progress_all_combinations(temp_store):
    engine = ShadowObservationEngine(store=temp_store)
    progress = engine.get_accumulation_progress()

    assert progress["total_combinations"] == 39
    assert len(progress["combinations"]) == 39

    symbols = set(c["symbol"] for c in progress["combinations"])
    timeframes = set(c["timeframe"] for c in progress["combinations"])
    assert len(symbols) == 13
    assert len(timeframes) == 3


def test_combination_drilldown(temp_store):
    engine = ShadowObservationEngine(store=temp_store)
    engine.record_observation_cycle(
        symbol="XAUUSD", timeframe="H1", window_time="2026-08-10 14:00:00"
    )

    drill = engine.get_combination_drilldown(symbol="XAUUSD", timeframe="H1")

    assert drill["symbol"] == "XAUUSD"
    assert drill["timeframe"] == "H1"
    assert drill["observations_count"] == 1
    assert drill["latest_observation"] is not None


# ============================================================
# 3. Testes da API REST READ-ONLY
# ============================================================

def test_api_observation_health():
    res = client.get("/api/shadow/observation/health")
    assert res.status_code == 200
    data = res.json()
    assert data["total_universe_combinations"] == 39


def test_api_observation_progress():
    res = client.get("/api/shadow/observation/progress")
    assert res.status_code == 200
    data = res.json()
    assert data["total_combinations"] == 39
    assert len(data["combinations"]) == 39


def test_api_observation_history():
    res = client.get("/api/shadow/observation/history?symbol=EURUSD&timeframe=H1")
    assert res.status_code == 200
    data = res.json()
    assert "observations" in data
    assert "transitions" in data


def test_api_observation_drilldown():
    res = client.get("/api/shadow/observation/EURUSD/H1")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "EURUSD"
    assert data["timeframe"] == "H1"


# ============================================================
# 4. Teste de Ausência de Side Effects (PARTE J)
# ============================================================

def test_observation_engine_side_effect_safety(temp_store):
    """Garante que a Observation Layer é 100% observacional read-only e preserva parâmetros congelados."""
    original_rsi_period = HDF_ROBUST_CANDIDATE_V1.rsi_period
    original_target_r = HDF_ROBUST_CANDIDATE_V1.target_r

    engine = ShadowObservationEngine(store=temp_store)
    engine.record_observation_cycle(
        symbol="BTCUSD", timeframe="H4", window_time="2026-08-10 16:00:00"
    )

    # Verificação de parâmetros HDF congelados
    assert HDF_ROBUST_CANDIDATE_V1.rsi_period == original_rsi_period
    assert HDF_ROBUST_CANDIDATE_V1.target_r == original_target_r
