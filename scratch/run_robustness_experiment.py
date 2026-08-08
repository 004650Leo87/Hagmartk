from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import json
import MetaTrader5 as mt5
import pandas as pd

from backend.backtest.laboratory import QuantitativeRobustnessLab
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


def run_robustness_audit():
    print("=== CONECTANDO AO MT5 PARA OBTER DADOS XAUUSD D1 ===")
    if not mt5.initialize():
        print(f"Erro ao inicializar MT5: {mt5.last_error()}")
        return

    symbol = "XAUUSD"
    timeframe_str = "D1"
    tf = mt5.TIMEFRAME_D1

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 10000)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("Erro ao obter dados MT5")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

    strategy = HagmartkTrendReferenceStrategy()
    costs = CostsConfig(
        spread_points=25.0,
        point_value=0.01,
        commission_per_trade=0.0,
        slippage_points=5.0,
        swap_per_bar=0.0,
    )

    lab = QuantitativeRobustnessLab(
        strategy=strategy,
        symbol=symbol,
        timeframe=timeframe_str,
        costs=costs,
        intrabar_policy=IntrabarPolicy.CONSERVATIVE,
    )

    print("=== EXECUTANDO AUDITORIA QUANTITATIVA COMPLETA DE ROBUSTEZ ===")
    report = lab.run_full_robustness_audit(
        df,
        run_parameter_grid=True,
        monte_carlo_sims=10000,
        monte_carlo_seed=42,
    )

    output = {
        "status": report.status,
        "reconciliation_passed": report.reconciliation.passed,
        "total_trades": report.metrics_overall.total_trades if report.metrics_overall else 0,
        "net_result": report.metrics_overall.net_result if report.metrics_overall else 0.0,
        "profit_factor": report.metrics_overall.profit_factor if report.metrics_overall else 0.0,
        "win_rate": report.metrics_overall.win_rate if report.metrics_overall else 0.0,
        "new_metrics": report.new_metrics,
        "long_vs_short": report.long_vs_short,
        "concentration": {
            "top_1_contribution_pct": report.concentration.top_1_contribution_pct,
            "top_3_contribution_pct": report.concentration.top_3_contribution_pct,
            "top_5_contribution_pct": report.concentration.top_5_contribution_pct,
            "profit_without_best": report.concentration.outliers.profit_without_best,
            "profit_without_top_3": report.concentration.outliers.profit_without_top_3,
            "profit_without_top_5": report.concentration.outliers.profit_without_top_5,
            "mean_R_without_best": report.concentration.outliers.mean_R_without_best,
            "mean_R_without_top_3": report.concentration.outliers.mean_R_without_top_3,
            "mean_R_without_top_5": report.concentration.outliers.mean_R_without_top_5,
            "concentration_risk": report.concentration.concentration_risk,
        },
        "walk_forward": {
            "num_windows": report.walk_forward.num_windows,
            "overall_out_of_sample_net": report.walk_forward.overall_out_of_sample_net,
            "overall_out_of_sample_trades": report.walk_forward.overall_out_of_sample_trades,
            "stability_pass": report.walk_forward.stability_pass,
            "windows": [
                {
                    "window": w.window_id,
                    "train_net": w.net_result_train,
                    "test_net": w.net_result_test,
                    "train_pf": w.profit_factor_train,
                    "test_pf": w.profit_factor_test,
                }
                for w in report.walk_forward.windows
            ],
        },
        "monte_carlo": {
            "num_simulations": report.monte_carlo.num_simulations,
            "final_R_dist": report.monte_carlo.final_R_distribution.__dict__,
            "expectancy_R_dist": report.monte_carlo.expectancy_R_distribution.__dict__,
            "max_dd_R_dist": report.monte_carlo.max_drawdown_R_distribution.__dict__,
            "prob_final_loss_pct": report.monte_carlo.prob_final_loss_pct,
            "prob_dd_exceeds_5R_pct": report.monte_carlo.prob_drawdown_exceeds_20pct,
            "prob_dd_exceeds_10R_pct": report.monte_carlo.prob_drawdown_exceeds_30pct,
        },
        "parameter_robustness": {
            "grid_size": report.parameter_robustness.grid_size,
            "positive_combinations_pct": report.parameter_robustness.positive_combinations_pct,
            "is_stable_region": report.parameter_robustness.is_stable_region,
        },
        "component_audit": report.component_audit.__dict__ if report.component_audit else None,
        "final_classification": report.final_classification,
        "statistical_limitations": report.statistical_limitations,
        "possible_overfitting_signals": report.possible_overfitting_signals,
    }

    print("\n=== RELATÓRIO DO LABORATÓRIO DE ROBUSTEZ QUANTITATIVA ===")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    run_robustness_audit()
