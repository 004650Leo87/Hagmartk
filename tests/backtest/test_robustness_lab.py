from __future__ import annotations

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from backend.backtest.concentration import analyze_concentration_and_outliers
from backend.backtest.laboratory import QuantitativeRobustnessLab
from backend.backtest.monte_carlo import run_monte_carlo_bootstrap
from backend.backtest.parameter_robustness import evaluate_parameter_robustness_grid
from backend.backtest.reconciliation import reconcile_backtest
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation, simulate_trade_outcome
from backend.backtest.walk_forward import run_walk_forward_analysis
from backend.domain.events import Direction, StrategyEvent
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


def create_synthetic_candles(num_bars: int = 150, base_price: float = 100.0) -> pd.DataFrame:
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(num_bars):
        t = base_time + timedelta(days=i)
        rows.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "open": base_price,
            "high": base_price + 1.0,
            "low": base_price - 1.0,
            "close": base_price,
            "tick_volume": 1000,
        })
    return pd.DataFrame(rows)


def test_1_walk_forward_sem_vazamento_temporal():
    df = create_synthetic_candles(150, 100.0)
    # Adiciona rompimentos sintéticos
    df.iloc[76, df.columns.get_loc("high")] = 105.0
    df.iloc[110, df.columns.get_loc("high")] = 110.0

    strat = HagmartkTrendReferenceStrategy()
    wf_report = run_walk_forward_analysis(
        df=df,
        strategy=strat,
        symbol="XAUUSD",
        timeframe="D1",
        num_windows=2,
    )
    assert wf_report.num_windows == 2
    for w in wf_report.windows:
        assert w.end_train <= w.start_test


def test_2_separacao_correta_train_test():
    df = create_synthetic_candles(150, 100.0)
    strat = HagmartkTrendReferenceStrategy()
    wf_report = run_walk_forward_analysis(
        df=df,
        strategy=strat,
        symbol="XAUUSD",
        timeframe="D1",
        train_ratio=0.70,
    )
    assert wf_report.train_ratio == 0.70
    assert abs(wf_report.test_ratio - 0.30) < 1e-4


def test_3_monte_carlo_reproduzivel_com_seed():
    evt = StrategyEvent(
        strategy_id="TEST", strategy_version="1.0", symbol="XAUUSD", timeframe="D1",
        direction=Direction.BUY, detected_at="2026-01-01", reference_price=100.0, invalidation=95.0
    )
    t1 = TradeSimulation("1", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=10.0, r_multiple_net=2.0)
    t2 = TradeSimulation("2", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=-5.0, r_multiple_net=-1.0)
    t3 = TradeSimulation("3", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=15.0, r_multiple_net=3.0)

    mc1 = run_monte_carlo_bootstrap([t1, t2, t3], num_simulations=1000, seed=42)
    mc2 = run_monte_carlo_bootstrap([t1, t2, t3], num_simulations=1000, seed=42)

    assert mc1.final_R_distribution.p50 == mc2.final_R_distribution.p50
    assert mc1.prob_final_loss_pct == mc2.prob_final_loss_pct


def test_4_calculo_correto_percentis():
    evt = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)
    trades = [TradeSimulation(f"{i}", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=float(i), r_multiple_net=float(i)) for i in range(1, 10)]

    mc = run_monte_carlo_bootstrap(trades, num_simulations=500, seed=42)
    dist = mc.final_R_distribution
    assert dist.p5 <= dist.p25 <= dist.p50 <= dist.p75 <= dist.p95


def test_5_deteccao_concentracao():
    evt = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)
    # Trade 1 responde por 80 de um lucro total de 100 (80%)
    t1 = TradeSimulation("1", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=80.0, r_multiple_net=8.0, entry_time="2026-01-01")
    t2 = TradeSimulation("2", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=10.0, r_multiple_net=1.0, entry_time="2026-01-02")
    t3 = TradeSimulation("3", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=10.0, r_multiple_net=1.0, entry_time="2026-01-03")

    conc = analyze_concentration_and_outliers([t1, t2, t3])
    assert conc.top_1_contribution_pct == 80.0
    assert conc.concentration_risk == "EXTREME"


def test_6_remocao_correta_melhores_trades():
    evt = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)
    t1 = TradeSimulation("1", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=100.0, r_multiple_net=10.0, entry_time="2026-01-01")
    t2 = TradeSimulation("2", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=-20.0, r_multiple_net=-2.0, entry_time="2026-01-02")
    t3 = TradeSimulation("3", evt, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=-30.0, r_multiple_net=-3.0, entry_time="2026-01-03")

    conc = analyze_concentration_and_outliers([t1, t2, t3])
    assert conc.outliers.original_net_profit == 50.0
    assert conc.outliers.profit_without_best == -50.0  # Sem o trade 1, o resultado fica -50.0


def test_7_breakdown_long_short():
    evt_b = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)
    evt_s = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.SELL, "2026-01-01", 100.0, invalidation=105.0)

    t_long = TradeSimulation("1", evt_b, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=50.0, r_multiple_net=5.0)
    t_short = TradeSimulation("2", evt_s, IntrabarPolicy.CONSERVATIVE, CostsConfig(), net_profit=-10.0, r_multiple_net=-1.0)

    df = create_synthetic_candles(100, 100.0)
    lab = QuantitativeRobustnessLab(HagmartkTrendReferenceStrategy(), "XAUUSD", "D1")
    report = lab.run_full_robustness_audit(df, run_parameter_grid=False, monte_carlo_sims=100)

    assert "LONG" in report.long_vs_short
    assert "SHORT" in report.long_vs_short


def test_8_sample_size_warning():
    df = create_synthetic_candles(100, 100.0)
    lab = QuantitativeRobustnessLab(HagmartkTrendReferenceStrategy(), "XAUUSD", "D1")
    report = lab.run_full_robustness_audit(df, run_parameter_grid=False, monte_carlo_sims=100)

    assert report.component_audit is not None
    assert report.component_audit.sample_size_classification in ("INSUFFICIENT_SAMPLE", "LOW_SAMPLE")
    assert report.final_classification in ("ROBUSTNESS_NOT_EVALUABLE", "PROMISING_BUT_INSUFFICIENT", "FRAGILE")



def test_9_parameter_robustness():
    df = create_synthetic_candles(100, 100.0)
    df.iloc[76, df.columns.get_loc("high")] = 105.0

    report = evaluate_parameter_robustness_grid(
        df=df,
        symbol="XAUUSD",
        timeframe="D1",
        entry_lookbacks=[50, 55],
        exit_lookbacks=[20],
        atr_periods=[20],
        stop_multipliers=[2.0],
    )
    assert report.grid_size == 2
    assert len(report.results) > 0


def test_10_reconciliacao_obrigatoria():
    evt = StrategyEvent("TEST", "1.0", "XAUUSD", "D1", Direction.BUY, "2026-01-01", 100.0, invalidation=95.0)
    future = pd.DataFrame([{"time": "2026-01-02", "open": 101.0, "high": 110.0, "low": 99.0, "close": 108.0}])
    sim = simulate_trade_outcome(evt, future, CostsConfig(spread_points=25.0, point_value=0.01, slippage_points=5.0))

    # Erro forçado no net_profit
    sim.net_profit += 999.0
    recon = reconcile_backtest([sim])
    assert recon.passed is False


def test_11_matematica_trend_reference_preservada():
    strat = HagmartkTrendReferenceStrategy()
    assert strat.strategy_id == "hagmartk_trend_reference"
    assert strat.entry_lookback == 55
    assert strat.exit_lookback == 20
    assert strat.atr_period == 20
    assert strat.stop_n_multiplier == 2.0
