from __future__ import annotations

import pandas as pd
import pytest

from backend.backtest.exit_study import (
    ExitPolicyConfig,
    ExitPolicyType,
    calculate_exit_policy_metrics,
    simulate_exit_policy_on_occurrence,
)
from backend.strategies.hdf.models import HDFOccurrence, HDFState, HDFTemporalModel, ReversalPatternType


def create_dummy_occurrence(
    entry_price: float = 100.0,
    initial_stop: float = 90.0,
    direction: str = "BULLISH",
) -> HDFOccurrence:
    return HDFOccurrence(
        occurrence_id="TEST_OCC_1",
        symbol="EURUSD",
        timeframe="H1",
        direction=direction,
        state=HDFState.ACTIVATED,
        temporal_model=HDFTemporalModel(
            pivot_1_time="2026-01-01 08:00:00",
            pivot_2_time="2026-01-01 09:00:00",
            armed_at="2026-01-01 09:00:00",
            entry_at="2026-01-01 10:00:00",
        ),
        variant="HDF_DVP",
        pattern_type=ReversalPatternType.BULLISH_ENGULFING,
        entry_price=entry_price,
        initial_stop=initial_stop,
        initial_risk=abs(entry_price - initial_stop),
        activation_level=100.0,
        bars_to_activation=1,
    )


def test_1_target_hit_before_stop():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)  # Risk = 10.0
    # Target 1.0R = 110.0
    fwd = pd.DataFrame([
        {"time": "2026-01-01 11:00:00", "open": 100.5, "high": 105.0, "low": 99.5, "close": 104.0},
        {"time": "2026-01-01 12:00:00", "open": 104.0, "high": 112.0, "low": 103.0, "close": 111.0},
    ])
    cfg = ExitPolicyConfig("EXIT_1R", ExitPolicyType.FIXED_TARGET, target_r=1.0)
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    assert res.status == "WIN"
    assert res.exit_reason == "TARGET"
    assert res.gross_r == 1.0
    assert pytest.approx(res.net_r, 0.001) == 0.97
    assert res.holding_bars == 2
    assert res.target_hit is True
    assert res.stopped is False


def test_2_stop_before_target():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    fwd = pd.DataFrame([
        {"time": "2026-01-01 11:00:00", "open": 99.0, "high": 99.5, "low": 88.0, "close": 89.0},
    ])
    cfg = ExitPolicyConfig("EXIT_1R", ExitPolicyType.FIXED_TARGET, target_r=1.0)
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    assert res.status == "LOSS"
    assert res.exit_reason == "STOP"
    assert res.gross_r == -1.0
    assert pytest.approx(res.net_r, 0.001) == -1.03
    assert res.holding_bars == 1
    assert res.stopped is True


def test_3_same_bar_stop_first_conflict():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    # Candle toca 115 (alvo 1.5R) e 85 (stop) no mesmo candle
    fwd = pd.DataFrame([
        {"time": "2026-01-01 11:00:00", "open": 100.0, "high": 115.0, "low": 85.0, "close": 95.0},
    ])
    cfg = ExitPolicyConfig("EXIT_1_5R", ExitPolicyType.FIXED_TARGET, target_r=1.5, intrabar_policy="STOP_FIRST")
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    assert res.status == "LOSS"
    assert res.exit_reason == "STOP"
    assert res.gross_r == -1.0
    assert res.stopped is True


def test_4_partial_50_math_and_runner():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    # Candle 1: toca 105 (0.5R parcial)
    # Candle 2: toca 120 (2.0R runner)
    fwd = pd.DataFrame([
        {"time": "2026-01-01 11:00:00", "open": 100.0, "high": 106.0, "low": 99.0, "close": 105.0},
        {"time": "2026-01-01 12:00:00", "open": 105.0, "high": 122.0, "low": 104.0, "close": 121.0},
    ])
    cfg = ExitPolicyConfig("P50_0_5R_RUNNER", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=0.5, runner_target_r=2.0)
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    # 50% * 0.5R + 50% * 2.0R = 0.25R + 1.0R = 1.25R bruto
    assert res.status == "WIN"
    assert res.exit_reason == "PARTIAL_RUNNER"
    assert pytest.approx(res.gross_r, 0.001) == 1.25
    assert pytest.approx(res.net_r, 0.001) == 1.22


def test_5_runner_stopped_after_partial():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    # Candle 1: toca 110 (1.0R parcial)
    # Candle 2: cai para 88 (stop estrutural)
    fwd = pd.DataFrame([
        {"time": "2026-01-01 11:00:00", "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0},
        {"time": "2026-01-01 12:00:00", "open": 108.0, "high": 108.0, "low": 88.0, "close": 89.0},
    ])
    cfg = ExitPolicyConfig("P50_1R_RUNNER", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=1.0, runner_target_r=2.0)
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    # 50% * 1.0R + 50% * (-1.0R) = 0.5R - 0.5R = 0.0R bruto
    assert pytest.approx(res.gross_r, 0.001) == 0.0
    assert pytest.approx(res.net_r, 0.001) == -0.03


def test_6_time_exit():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    # 5 candles sem bater stop 90 nem alvo fixo. No candle 5 close é 108 (+0.8R)
    fwd_rows = []
    for i in range(5):
        fwd_rows.append({"time": f"2026-01-01 1{i}:00:00", "open": 100.0 + i, "high": 102.0 + i, "low": 98.0 + i, "close": 101.0 + i * 1.75})
    fwd = pd.DataFrame(fwd_rows)

    cfg = ExitPolicyConfig("TIME_EXIT_5", ExitPolicyType.TIME_EXIT, time_horizon_bars=5)
    res = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    assert res.status == "WIN"
    assert res.exit_reason == "TIME_EXIT"
    assert res.holding_bars == 5
    expected_gross = (108.0 - 100.0) / 10.0  # +0.8 R
    assert pytest.approx(res.gross_r, 0.001) == expected_gross


def test_7_reconciliation_and_accounting():
    occ = create_dummy_occurrence(entry_price=100.0, initial_stop=90.0)
    fwd = pd.DataFrame([{"time": "2026-01-01 11:00:00", "open": 100.0, "high": 115.0, "low": 99.0, "close": 112.0}])
    cfg = ExitPolicyConfig("EXIT_1R", ExitPolicyType.FIXED_TARGET, target_r=1.0)
    res1 = simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.03)

    m = calculate_exit_policy_metrics([res1], "EXIT_1R")
    assert pytest.approx(m.gross_r - m.costs_r, 0.001) == m.net_r
    assert m.total_trades == 1
    assert m.wins == 1
