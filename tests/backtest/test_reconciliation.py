from __future__ import annotations

import pytest
import pandas as pd

from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation, simulate_trade_outcome
from backend.backtest.reconciliation import reconcile_backtest
from backend.domain.events import Direction, StrategyEvent


def test_reconciliation_exact_accounting():
    """Valida que net_pnl = true_gross_pnl - total_costs para operações long e short."""
    evt_buy = StrategyEvent(
        strategy_id="TEST",
        strategy_version="1.0",
        symbol="XAUUSD",
        timeframe="D1",
        direction=Direction.BUY,
        detected_at="2026-01-01T10:00:00",
        reference_price=100.0,
        invalidation=95.0,
        metadata={"breakout_level": 100.0, "initial_risk": 5.0},
    )

    future_buy = pd.DataFrame([{"time": "2026-01-02", "open": 101.0, "high": 110.0, "low": 99.0, "close": 108.0}])
    costs = CostsConfig(spread_points=25.0, point_value=0.01, slippage_points=5.0)  # spread 0.25, slippage 0.05

    sim_buy = simulate_trade_outcome(evt_buy, future_buy, costs)
    report = reconcile_backtest([sim_buy])

    assert report.passed is True
    assert report.trades_with_errors == 0
    assert report.net_difference == pytest.approx(0.0)


def test_reconciliation_detects_mismatch():
    """Valida que o relatorio de reconciliação detecta erros contábeis forçados."""
    evt = StrategyEvent(
        strategy_id="TEST",
        strategy_version="1.0",
        symbol="XAUUSD",
        timeframe="D1",
        direction=Direction.BUY,
        detected_at="2026-01-01T10:00:00",
        reference_price=100.0,
        invalidation=95.0,
        metadata={"breakout_level": 100.0, "initial_risk": 5.0},
    )
    future = pd.DataFrame([{"time": "2026-01-02", "open": 101.0, "high": 110.0, "low": 99.0, "close": 108.0}])
    sim = simulate_trade_outcome(evt, future, CostsConfig(spread_points=25.0, point_value=0.01, slippage_points=5.0))

    # Força um erro contábil no net_profit
    sim.net_profit += 10.0

    report = reconcile_backtest([sim])
    assert report.passed is False
    assert report.trades_with_errors == 1
