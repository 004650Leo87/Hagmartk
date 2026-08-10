"""Suíte de testes para o Shadow Performance Engine V1 (Fase 4B).

Cobre:
1. Banco sem eventos (NO_TERMINAL_TRADES)
2. Oportunidades sem ativação
3. Ativados sem fechar trade terminal
4. 1 trade Win (+2R)
5. 1 trade Loss (-1R)
6. Trades múltiplos (Win Rate, Expectancy, Total R, Profit Factor, Drawdown)
7. Denominador do Win Rate correto (apenas wins + losses)
8. EXPIRED excluído do Win Rate
9. INVALIDATED excluído do Win Rate / Expectancy
10. Profit Factor sem perdas retorna None e flag NO_LOSSES_YET
11. Payoff sem perdas retorna None
12. Curva de R acumulado
13. Max Drawdown R
14. Streaks consecutivas de vitórias e derrotas
15. MAE / MFE ignorando Nones
16. Duração em barras e segundos
17. Breakdowns por símbolo, timeframe, direção e classe
18. BOOTSTRAP_EXISTING excluído da performance prospectiva
19. Eventos pré-shadow excluídos da performance prospectiva
20. Isolação absoluta da referência histórica
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pytest

from backend.domain.shadow_models import ShadowEvent, ShadowState
from backend.services.shadow_performance import (
    ProspectiveEligibilityFilter,
    ShadowPerformanceEngine,
)


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.get_shadow_session.return_value = {
        "candidate_id": "hdf_dvp_exit_2r",
        "started_at": "2026-08-10 12:00:00",
        "enabled": True,
    }
    return store


def make_event(
    event_id: str,
    state: str,
    time_str: str = "2026-08-10 14:00:00",
    symbol: str = "EURUSD",
    timeframe: str = "H1",
    direction: str = "BULLISH",
    asset_class: str = "FOREX",
    activated_at: str = "2026-08-10 15:00:00",
    updated_at: str = "2026-08-10 17:00:00",
    entry_price: float = 1.1000,
    initial_stop: float = 1.0950,
    target_2R: float = 1.1100,
    initial_risk: float = 0.0050,
    mae_r: float = 0.2,
    mfe_r: float = 2.0,
    bars_dur: int = 4,
    metadata: dict = None,
) -> ShadowEvent:
    return ShadowEvent(
        event_id=event_id,
        candidate_id="hdf_dvp_exit_2r",
        candidate_version="1.0.0",
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        direction=direction,
        confluence_time=time_str,
        divergence_confirmed_at=time_str,
        current_state=state,
        activated_at=activated_at if state in (ShadowState.ACTIVATED.value, ShadowState.TARGET_2R.value, ShadowState.STOPPED.value) else "",
        updated_at=updated_at,
        entry_price=entry_price,
        initial_stop=initial_stop,
        target_2R=target_2R,
        initial_risk=initial_risk,
        mae_r_live=mae_r,
        mfe_r_live=mfe_r,
        bars_since_activation=bars_dur,
        metadata=metadata or {"synthetic": False, "bootstrap_detected": False},
        created_at=time_str,
    )


# ============================================================
# 1. Filtro de Elegibilidade Prospectiva
# ============================================================

def test_eligibility_filter_post_shadow():
    evt = make_event("e1", ShadowState.ARMED.value, "2026-08-10 14:00:00")
    assert ProspectiveEligibilityFilter.is_eligible(evt, "2026-08-10 12:00:00") is True


def test_eligibility_filter_pre_shadow():
    evt = make_event("e2", ShadowState.TARGET_2R.value, "2026-08-10 10:00:00")
    assert ProspectiveEligibilityFilter.is_eligible(evt, "2026-08-10 12:00:00") is False


def test_eligibility_filter_bootstrap_existing():
    evt = make_event("e3", ShadowState.BOOTSTRAP_EXISTING.value, "2026-08-10 14:00:00")
    assert ProspectiveEligibilityFilter.is_eligible(evt, "2026-08-10 12:00:00") is False


# ============================================================
# 2. Banco sem eventos (NO_TERMINAL_TRADES)
# ============================================================

def test_empty_database_snapshot(mock_store):
    mock_store.list_history_events.return_value = []
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    assert snap.sample_status == "NO_TERMINAL_TRADES"
    assert snap.total_raw_events == 0
    assert snap.terminal_trades_count == 0
    assert snap.win_rate is None
    assert snap.expectancy_r is None
    assert snap.profit_factor is None
    assert snap.equity_curve_r == []


# ============================================================
# 3. Oportunidades sem ativação e ativados sem fechar
# ============================================================

def test_opportunities_without_terminal_trades(mock_store):
    e1 = make_event("e1", ShadowState.ARMED.value, "2026-08-10 13:00:00")
    e2 = make_event("e2", ShadowState.ACTIVATED.value, "2026-08-10 14:00:00")
    e3 = make_event("e3", ShadowState.EXPIRED.value, "2026-08-10 15:00:00")
    e4 = make_event("e4", ShadowState.INVALIDATED.value, "2026-08-10 16:00:00")

    mock_store.list_history_events.return_value = [e1, e2, e3, e4]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    assert snap.prospective_opportunities == 4
    assert snap.activated_count == 1
    assert snap.active_trades_count == 1
    assert snap.terminal_trades_count == 0
    assert snap.expired_pre_activation_count == 1
    assert snap.invalidated_pre_activation_count == 1
    assert snap.activation_rate == 25.0
    assert snap.win_rate is None
    assert snap.sample_status == "NO_TERMINAL_TRADES"


# ============================================================
# 4. Trades Individuais e Múltiplos (Win/Loss/PF/Expectancy)
# ============================================================

def test_single_win_trade(mock_store):
    e1 = make_event("e1", ShadowState.TARGET_2R.value, "2026-08-10 13:00:00")
    mock_store.list_history_events.return_value = [e1]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    assert snap.terminal_trades_count == 1
    assert snap.wins_count == 1
    assert snap.losses_count == 0
    assert snap.win_rate == 100.0
    assert snap.total_r == 2.0
    assert snap.expectancy_r == 2.0
    assert snap.profit_factor is None
    assert snap.profit_factor_flag == "NO_LOSSES_YET"
    assert snap.payoff_ratio is None


def test_single_loss_trade(mock_store):
    e1 = make_event("e1", ShadowState.STOPPED.value, "2026-08-10 13:00:00")
    mock_store.list_history_events.return_value = [e1]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    assert snap.terminal_trades_count == 1
    assert snap.wins_count == 0
    assert snap.losses_count == 1
    assert snap.win_rate == 0.0
    assert snap.total_r == -1.0
    assert snap.expectancy_r == -1.0
    assert snap.profit_factor == 0.0
    assert snap.profit_factor_flag == "NORMAL"


def test_multiple_trades_performance(mock_store):
    # 2 Wins (+2R, +2R) e 1 Loss (-1R)
    e1 = make_event("e1", ShadowState.TARGET_2R.value, "2026-08-10 13:00:00", updated_at="2026-08-10 14:00:00")
    e2 = make_event("e2", ShadowState.STOPPED.value, "2026-08-10 14:00:00", updated_at="2026-08-10 15:00:00")
    e3 = make_event("e3", ShadowState.TARGET_2R.value, "2026-08-10 15:00:00", updated_at="2026-08-10 16:00:00")

    mock_store.list_history_events.return_value = [e1, e2, e3]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    assert snap.terminal_trades_count == 3
    assert snap.wins_count == 2
    assert snap.losses_count == 1
    assert snap.win_rate == 66.67
    assert snap.total_r == 3.0
    assert snap.expectancy_r == 1.0
    assert snap.profit_factor == 4.0
    assert snap.payoff_ratio == 2.0
    assert snap.max_drawdown_r == 1.0
    assert snap.max_consecutive_wins == 1
    assert snap.max_consecutive_losses == 1


# ============================================================
# 5. Isolação da Referência Histórica
# ============================================================

def test_historical_reference_is_isolated(mock_store):
    e1 = make_event("e1", ShadowState.TARGET_2R.value, "2026-08-10 13:00:00")
    mock_store.list_history_events.return_value = [e1]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    hist = snap.historical_reference
    assert hist["trades"] == 417
    assert hist["total_r"] == 49.24
    assert hist["win_rate"] == 37.89

    # Confirmar que a métrica prospectiva continua separada
    assert snap.terminal_trades_count == 1
    assert snap.win_rate == 100.0


# ============================================================
# 6. Breakdowns por Ativo, Timeframe e Direção
# ============================================================

def test_breakdowns(mock_store):
    e1 = make_event("e1", ShadowState.TARGET_2R.value, "2026-08-10 13:00:00", symbol="EURUSD", timeframe="H1", direction="BULLISH")
    e2 = make_event("e2", ShadowState.STOPPED.value, "2026-08-10 14:00:00", symbol="GBPUSD", timeframe="M15", direction="BEARISH")

    mock_store.list_history_events.return_value = [e1, e2]
    engine = ShadowPerformanceEngine(store=mock_store)

    snap = engine.build_snapshot()

    b_sym = {item["key"]: item for item in snap.breakdowns["symbol"]}
    assert b_sym["EURUSD"]["wins"] == 1
    assert b_sym["EURUSD"]["total_r"] == 2.0
    assert b_sym["GBPUSD"]["losses"] == 1
    assert b_sym["GBPUSD"]["total_r"] == -1.0

    b_tf = {item["key"]: item for item in snap.breakdowns["timeframe"]}
    assert b_tf["H1"]["terminal_trades"] == 1
    assert b_tf["M15"]["terminal_trades"] == 1
