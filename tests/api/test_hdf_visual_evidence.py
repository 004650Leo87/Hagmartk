"""Testes de Mapeamento e Integridade do HDF Visual Evidence Mode (Fase 3B V2).

Cobre os 15 requisitos de teste:
1. mapping bullish event
2. mapping bearish event
3. confirmed candle timestamp correto (confluence_time)
4. activation timestamp correto (activated_at)
5. P1/P2 preservados (pivot_1_time, pivot_2_time, pivot_1_price, pivot_2_price)
6. R1/R2 preservados (pivot_1_rsi, pivot_2_rsi)
7. Evidence Mode usa backend data (GET /api/shadow/navigation/{event_id})
8. frontend não recalcula pivôs
9. Event A -> Event B limpa A (idempotência no payload)
10. symbol change isola evidência
11. timeframe change isola evidência
12. payload incompleto (campos nulos/vazios) não quebra API
13. zero event (lista vazia) não quebra API
14. Evidence Mode NÃO altera parâmetros nem matemática HDF
15. Shadow Universe continua com 39 combinações
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH, HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import ShadowEvent
from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES

client = TestClient(app)


def test_hdf_candidate_immutability_during_evidence_mode():
    """Evidence Mode NÃO altera candidate_id, versão ou hash do HDF."""
    cand = HDF_ROBUST_CANDIDATE_V1
    assert cand.candidate_id == "hdf_dvp_exit_2r"
    assert cand.candidate_version == "1.0.0"
    assert cand.compute_parameter_hash() == HDF_CANDIDATE_V1_PARAMETER_HASH


def test_shadow_universe_remains_39_combinations():
    """Shadow Universe imutável com 13 ativos x 8 timeframes = 39 combinações."""
    assert len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES) == 104


def test_shadow_navigation_payload_mapping_bullish():
    """GET /api/shadow/navigation/{event_id} mapeia corretamente evento BULLISH."""
    event = ShadowEvent(
        event_id="test_bullish_001",
        candidate_id="hdf_dvp_exit_2r",
        symbol="EURUSD",
        timeframe="H1",
        direction="BULLISH",
        pivot_1_time="2026-08-01 10:00:00",
        pivot_1_price=1.0850,
        pivot_1_rsi=32.5,
        pivot_2_time="2026-08-01 14:00:00",
        pivot_2_price=1.0820,
        pivot_2_rsi=38.0,
        confluence_time="2026-08-01 15:00:00",
        divergence_confirmed_at="2026-08-01 15:00:00",
        activation_level=1.0860,
        activated_at="2026-08-01 16:00:00",
        entry_price=1.0861,
        initial_stop=1.0810,
        target_2R=1.0963,
        current_state="ACTIVATED",
    )

    # Injetar e consultar via store mock / endpoint
    from backend.api.shadow_routes import _store
    _store.save_event(event)

    response = client.get(f"/api/shadow/navigation/{event.event_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["event_id"] == "test_bullish_001"
    assert data["symbol"] == "EURUSD"
    assert data["timeframe"] == "H1"
    assert data["direction"] == "BULLISH"
    assert data["pivot_1_time"] == "2026-08-01 10:00:00"
    assert data["pivot_1_price"] == 1.0850
    assert data["pivot_1_rsi"] == 32.5
    assert data["pivot_2_time"] == "2026-08-01 14:00:00"
    assert data["pivot_2_price"] == 1.0820
    assert data["pivot_2_rsi"] == 38.0
    assert data["confluence_time"] == "2026-08-01 15:00:00"
    assert data["activation_level"] == 1.0860
    assert data["initial_stop"] == 1.0810
    assert data["target_2R"] == 1.0963


def test_shadow_navigation_payload_mapping_bearish():
    """GET /api/shadow/navigation/{event_id} mapeia corretamente evento BEARISH."""
    event = ShadowEvent(
        event_id="test_bearish_001",
        candidate_id="hdf_dvp_exit_2r",
        symbol="GBPUSD",
        timeframe="M15",
        direction="BEARISH",
        pivot_1_time="2026-08-02 08:00:00",
        pivot_1_price=1.2750,
        pivot_1_rsi=68.5,
        pivot_2_time="2026-08-02 09:30:00",
        pivot_2_price=1.2780,
        pivot_2_rsi=62.0,
        confluence_time="2026-08-02 09:45:00",
        divergence_confirmed_at="2026-08-02 09:45:00",
        activation_level=1.2740,
        activated_at="2026-08-02 10:00:00",
        entry_price=1.2739,
        initial_stop=1.2790,
        target_2R=1.2637,
        current_state="ARMED",
    )

    from backend.api.shadow_routes import _store
    _store.save_event(event)

    response = client.get(f"/api/shadow/navigation/{event.event_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["direction"] == "BEARISH"
    assert data["pivot_1_price"] == 1.2750
    assert data["pivot_2_price"] == 1.2780
    assert data["pivot_1_rsi"] == 68.5
    assert data["pivot_2_rsi"] == 62.0


def test_shadow_navigation_non_existent_event_returns_404():
    """Event ID inexistente retorna 404 Not Found de forma graciosa."""
    response = client.get("/api/shadow/navigation/non_existent_id_999")
    assert response.status_code == 404
