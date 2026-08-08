from __future__ import annotations

import pytest

from backend.backtest.exit_study import TradeExitResult
from backend.backtest.stage2_robustness import (
    Stage2PolicyReport,
    analyze_concentration_and_outliers,
    analyze_leave_one_asset_out,
    classify_stage2_policy,
    run_monte_carlo_bootstrap,
)


def test_1_monte_carlo_determinism():
    sample_rs = [1.5, -1.0, 2.0, -1.0, 0.5, 3.0, -1.0, 1.2, -1.0, 0.8]
    r1 = run_monte_carlo_bootstrap(sample_rs, iterations=1000, seed=42)
    r2 = run_monte_carlo_bootstrap(sample_rs, iterations=1000, seed=42)

    assert r1.prob_net_loss == r2.prob_net_loss
    assert r1.median_final_r == r2.median_final_r
    assert r1.p95_max_dd_r == r2.p95_max_dd_r


def test_2_concentration_analysis():
    trades = [
        TradeExitResult("1", "EURUSD", "FOREX", "H1", "ENG", "<1.0", "BULLISH", "LONDON", 1.0, 0.9, 0.1, "WIN", "TARGET", 10.0, 0.03, 9.97, 1, False, True),
        TradeExitResult("2", "EURUSD", "FOREX", "H1", "ENG", "<1.0", "BULLISH", "LONDON", 1.0, 0.9, 0.1, "LOSS", "STOP", -1.0, 0.03, -1.03, 1, True, False),
        TradeExitResult("3", "EURUSD", "FOREX", "H1", "ENG", "<1.0", "BULLISH", "LONDON", 1.0, 0.9, 0.1, "WIN", "TARGET", 1.0, 0.03, 0.97, 1, False, True),
    ]

    conc = analyze_concentration_and_outliers(trades)
    assert conc.top1_pct > 80.0  # O trade 1 (9.97R) domina os lucros positivos
    assert conc.without_top1_net_r < conc.without_worst5_net_r


def test_3_leave_one_asset_out():
    trades = [
        TradeExitResult("1", "EURUSD", "FOREX", "H1", "ENG", "<1.0", "BULLISH", "LONDON", 1.0, 0.9, 0.1, "WIN", "TARGET", 5.0, 0.03, 4.97, 1, False, True),
        TradeExitResult("2", "BTCUSD", "CRYPTO", "H1", "ENG", "<1.0", "BULLISH", "LONDON", 1.0, 0.9, 0.1, "WIN", "TARGET", 1.0, 0.03, 0.97, 1, False, True),
    ]

    loo = analyze_leave_one_asset_out(trades)
    assert loo.largest_dependency_asset == "EURUSD"
    assert "EURUSD" in loo.asset_net_r_map
    assert "BTCUSD" in loo.asset_net_r_map


def test_4_stage2_classification_logic():
    rep = Stage2PolicyReport(policy_name="TEST", classification="", profit_factor=1.20, net_r=30.0)
    rep.monte_carlo.prob_net_loss = 2.0
    rep.oos.out_of_sample_pf = 1.15
    rep.cost_sensitivity.cost_2x_pf = 1.10
    rep.concentration.top3_pct = 30.0

    cls_res = classify_stage2_policy(rep)
    assert cls_res == "ROBUST_CANDIDATE"

    # Se Monte Carlo tiver alta probabilidade de perda
    rep.monte_carlo.prob_net_loss = 25.0
    cls_res_fragile = classify_stage2_policy(rep)
    assert cls_res_fragile == "FRAGILE"
