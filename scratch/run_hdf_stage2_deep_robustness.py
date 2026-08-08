from __future__ import annotations

import sys
import os
import time
from collections import defaultdict
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from backend.backtest.data_cache import OHLCDataCache
from backend.backtest.exit_study import (
    ExitPolicyConfig,
    ExitPolicyType,
    TradeExitResult,
    calculate_exit_policy_metrics,
    simulate_exit_policy_on_occurrence,
)
from backend.backtest.profiling import ExecutionProfiler
from backend.backtest.stage2_robustness import (
    CostSensitivityReport,
    LeaveOneOutReport,
    OutOfSampleReport,
    ParameterStabilityReport,
    ProductUsabilityReport,
    Stage2PolicyReport,
    analyze_concentration_and_outliers,
    analyze_leave_one_asset_out,
    classify_stage2_policy,
    run_monte_carlo_bootstrap,
)
from backend.strategies.hdf.strategy import HDFStrategy, PatternAssociationPolicy, VolumeObservationPolicy

FOREX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
FOREX_CROSSES = ["EURJPY", "GBPJPY"]
METALS = ["XAUUSD", "XAGUSD"]
CRYPTO = ["BTCUSD", "ETHUSD"]

ALL_ASSETS = FOREX_MAJORS + FOREX_CROSSES + METALS + CRYPTO
ALL_TIMEFRAMES = ["M15", "H1", "H4"]

POLICIES_TO_TEST = [
    ExitPolicyConfig("EXIT_2R", ExitPolicyType.FIXED_TARGET, target_r=2.0),
    ExitPolicyConfig("P50_1R_RUNNER", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=1.0, runner_target_r=2.0),
]


def run_hdf_stage2_deep_robustness():
    profiler = ExecutionProfiler()
    profiler.start_timer("total_time")
    profiler.start_timer("data_acquisition_time")

    cache = OHLCDataCache()
    strat_central = HDFStrategy(
        variant="HDF_DVP",
        rsi_period=14,
        pivot_left=2,
        pivot_right=2,
        min_bars_between_pivots=5,
        max_bars_between_pivots=50,
        volume_min_relative=1.0,
        max_activation_bars=5,
        activation_policy="NEXT_BAR",
        execution_buffer=0.0,
        stop_buffer=0.0,
        volume_observation_policy=VolumeObservationPolicy.CONFLUENCE_CANDLE,
        pattern_association_policy=PatternAssociationPolicy.SAME_BAR,
    )

    all_dataset_records = []  # List of tuples (symbol, tf, df, meta, analysis)
    all_activated_occ_records = []  # List of tuples (occ, fwd_df, is_oos)

    tot_bars = 0
    hashes_map = {}

    for symbol in ALL_ASSETS:
        for tf in ALL_TIMEFRAMES:
            df, meta = cache.load(symbol, tf)
            if df is None or df.empty:
                continue
            if len(df) > 10000:
                df = df.iloc[-10000:].reset_index(drop=True)

            tot_bars += len(df)
            hashes_map[f"{symbol}_{tf}"] = meta.dataset_hash if meta else ""

            analysis = strat_central.evaluate_full_dataset_analysis(df, symbol, tf)
            all_dataset_records.append((symbol, tf, df, meta, analysis))

            # Split In-Sample (Primeiros 70%) vs Out-of-Sample (Últimos 30%)
            n_bars = len(df)
            split_idx = int(n_bars * 0.7)

            for occ in analysis["occurrences"]:
                if occ.state.value == "ACTIVATED":
                    act_idx = occ.metadata.get("activation_bar_index")
                    if act_idx is not None and act_idx < len(df) - 1:
                        fwd_df = df.iloc[act_idx + 1 : min(act_idx + 21, len(df))].reset_index(drop=True)
                        is_oos = (act_idx >= split_idx)
                        all_activated_occ_records.append((occ, fwd_df, is_oos))

    profiler.stop_timer("data_acquisition_time")
    profiler.start_timer("backtest_time")

    print(f"=== HAGMARTK HDF STAGE 2 DEEP ROBUSTNESS V1 ===")
    print(f"Combinações Analisadas  : {len(all_dataset_records)}")
    print(f"Total Candles           : {tot_bars}")
    print(f"Total Activated Trades  : {len(all_activated_occ_records)}")
    print(f"Hashes de Dataset Válidos: {len(set(hashes_map.values()))} únicos\n")

    policy_reports: Dict[str, Stage2PolicyReport] = {}

    for cfg in POLICIES_TO_TEST:
        print(f"[{cfg.name}] Iniciando Reconciliação e Análise de Robustez Stage 2...")

        p_name = cfg.name
        rep = Stage2PolicyReport(policy_name=p_name)

        # 1. Simulação dos 417 trades na política
        trade_results: List[TradeExitResult] = []
        is_trades: List[TradeExitResult] = []
        oos_trades: List[TradeExitResult] = []

        for occ, fwd_df, is_oos in all_activated_occ_records:
            res_t = simulate_exit_policy_on_occurrence(occ, fwd_df, cfg, cost_per_trade_r=0.03)
            trade_results.append(res_t)
            if is_oos:
                oos_trades.append(res_t)
            else:
                is_trades.append(res_t)

        m_global = calculate_exit_policy_metrics(trade_results, p_name)
        rep.total_trades = m_global.total_trades
        rep.net_r = m_global.net_r
        rep.profit_factor = m_global.profit_factor_r
        rep.expectancy_r = m_global.expectancy_r
        rep.max_dd_r = m_global.max_drawdown_r

        # 2. Out-of-Sample Report
        m_is = calculate_exit_policy_metrics(is_trades, p_name)
        m_oos = calculate_exit_policy_metrics(oos_trades, p_name)
        rep.oos = OutOfSampleReport(
            in_sample_trades=m_is.total_trades, in_sample_net_r=m_is.net_r, in_sample_pf=m_is.profit_factor_r,
            out_of_sample_trades=m_oos.total_trades, out_of_sample_net_r=m_oos.net_r,
            out_of_sample_pf=m_oos.profit_factor_r, out_of_sample_expectancy_r=m_oos.expectancy_r,
            out_of_sample_max_dd_r=m_oos.max_drawdown_r,
        )

        # 3. Monte Carlo Bootstrap (10.000 iterações)
        net_rs = [t.net_r for t in trade_results]
        rep.monte_carlo = run_monte_carlo_bootstrap(net_rs, iterations=10000, seed=42)

        # 4. Concentração & Outliers
        rep.concentration = analyze_concentration_and_outliers(trade_results)

        # 5. Leave-One-Asset-Out
        rep.leave_one_out = analyze_leave_one_asset_out(trade_results)

        # 6. Sensibilidade a Custos (Baseline 0.03R, 1.5x 0.045R, 2x 0.060R)
        res_baseline = trade_results
        res_1_5x = [simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.045) for occ, fwd, _ in all_activated_occ_records]
        res_2x = [simulate_exit_policy_on_occurrence(occ, fwd, cfg, cost_per_trade_r=0.060) for occ, fwd, _ in all_activated_occ_records]

        m_b = calculate_exit_policy_metrics(res_baseline, p_name)
        m_1_5 = calculate_exit_policy_metrics(res_1_5x, p_name)
        m_2 = calculate_exit_policy_metrics(res_2x, p_name)

        rep.cost_sensitivity = CostSensitivityReport(
            cost_baseline_net_r=m_b.net_r, cost_baseline_pf=m_b.profit_factor_r,
            cost_1_5x_net_r=m_1_5.net_r, cost_1_5x_pf=m_1_5.profit_factor_r,
            cost_2x_net_r=m_2.net_r, cost_2x_pf=m_2.profit_factor_r,
        )

        # 7. Superfície de Vizinhança Paramétrica (Parameter Stability)
        # Testa 8 vizinhos em torno de (2, 2, 5, 50, 1.0)
        neighbors = [
            (1, 2, 5, 50, 1.0), (3, 2, 5, 50, 1.0),
            (2, 1, 5, 50, 1.0), (2, 3, 5, 50, 1.0),
            (2, 2, 3, 50, 1.0), (2, 2, 7, 50, 1.0),
            (2, 2, 5, 40, 1.0), (2, 2, 5, 60, 1.0),
        ]
        stable_cnt = 0
        for pl, pr, min_b, max_b, v_min in neighbors:
            strat_n = HDFStrategy(
                variant="HDF_DVP", pivot_left=pl, pivot_right=pr,
                min_bars_between_pivots=min_b, max_bars_between_pivots=max_b,
                volume_min_relative=v_min,
            )
            n_trades_list = []
            for sym_n, tf_n, df_n, _, _ in all_dataset_records:
                an_n = strat_n.evaluate_full_dataset_analysis(df_n, sym_n, tf_n)
                for occ_n in an_n["occurrences"]:
                    if occ_n.state.value == "ACTIVATED":
                        act_i = occ_n.metadata.get("activation_bar_index")
                        f_df = df_n.iloc[act_i + 1 : min(act_i + 21, len(df_n))].reset_index(drop=True) if act_i is not None else pd.DataFrame()
                        t_n = simulate_exit_policy_on_occurrence(occ_n, f_df, cfg, cost_per_trade_r=0.03)
                        n_trades_list.append(t_n)
            m_neighbor = calculate_exit_policy_metrics(n_trades_list, p_name)
            if m_neighbor.profit_factor_r >= 1.05 and m_neighbor.expectancy_r > 0:
                stable_cnt += 1

        rep.parameter_stability = ParameterStabilityReport(
            total_neighbors_tested=len(neighbors),
            stable_neighbors_count=stable_cnt,
            parameter_stability_pct=round((stable_cnt / len(neighbors)) * 100.0, 1),
        )

        # 8. Métricas de Produto / Usabilidade
        holdings = [t.holding_bars for t in trade_results]
        rep.product_metrics = ProductUsabilityReport(
            frequency_per_week=round(len(trade_results) / (tot_bars / (24 * 5 * 3)), 2),
            frequency_per_month=round(len(trade_results) / (tot_bars / (24 * 20 * 3)), 2),
            average_holding_bars=round(float(np.mean(holdings)), 1) if holdings else 0.0,
            median_holding_bars=round(float(np.median(holdings)), 1) if holdings else 0.0,
            median_time_to_1r_bars=round(float(np.median([t.holding_bars for t in trade_results if t.target_hit])), 1) if trade_results else 0.0,
            median_time_to_2r_bars=round(float(np.median([t.holding_bars for t in trade_results if t.target_hit])), 1) if trade_results else 0.0,
        )

        # 9. Classificação Final do Stage 2
        rep.classification = classify_stage2_policy(rep)
        policy_reports[p_name] = rep
        print(f"  [{p_name}] Concluído com Sucesso! Classificação: {rep.classification}")

    profiler.stop_timer("backtest_time")
    profiler.start_timer("reporting_time")

    # IMPRESSÃO DO RELATÓRIO FINAL
    print("\n==================================================")
    print("HDF STAGE 2 DEEP ROBUSTNESS V1 — RELATÓRIO EXECUTIVO")
    print("==================================================")

    for p_name, r in policy_reports.items():
        print(f"\n--- POLÍTICA: {p_name} ({r.classification}) ---")
        print(f"Trades Totais        : {r.total_trades}")
        print(f"Net R                : {r.net_r:.2f} R")
        print(f"Profit Factor (PF)   : {r.profit_factor:.2f}")
        print(f"Expectancy R         : {r.expectancy_r:.2f} R")
        print(f"Max Drawdown R       : {r.max_dd_r:.2f} R")
        print(f"Out-of-Sample PF     : {r.oos.out_of_sample_pf:.2f} (IS PF: {r.oos.in_sample_pf:.2f})")
        print(f"Monte Carlo Prob Loss: {r.monte_carlo.prob_net_loss:.1f}% (p95 MaxDD: {r.monte_carlo.p95_max_dd_r:.1f}R)")
        print(f"Top 3 Concentração   : {r.concentration.top3_pct:.1f}% (Net R sem Top3: {r.concentration.without_top3_net_r:.1f}R, PF: {r.concentration.without_top3_pf:.2f})")
        print(f"Estabilidade Vizinha : {r.parameter_stability.parameter_stability_pct}% ({r.parameter_stability.stable_neighbors_count}/{r.parameter_stability.total_neighbors_tested} vizinhos aprovados)")
        print(f"Sensibilidade Custos : Baseline PF={r.cost_sensitivity.cost_baseline_pf:.2f} | 1.5x PF={r.cost_sensitivity.cost_1_5x_pf:.2f} | 2.0x PF={r.cost_sensitivity.cost_2x_pf:.2f}")
        print(f"Maior Dependência    : Ativo {r.leave_one_out.largest_dependency_asset} (Net R sem ele: {r.leave_one_out.impact_when_removed_r:.1f}R)")

    print("\n==================================================")
    print("TABELA COMPARATIVA STAGE 2: EXIT_2R vs P50_1R_RUNNER")
    print("==================================================")
    rA = policy_reports["EXIT_2R"]
    rB = policy_reports["P50_1R_RUNNER"]
    print(f"{'Métrica / Teste':<28} | {'EXIT_2R':<18} | {'P50_1R_RUNNER':<18}")
    print("-" * 70)
    print(f"{'Classificação Stage 2':<28} | {rA.classification:<18} | {rB.classification:<18}")
    print(f"{'Net R Acumulado':<28} | {rA.net_r:<18.1f} | {rB.net_r:<18.1f}")
    print(f"{'Profit Factor (PF)':<28} | {rA.profit_factor:<18.2f} | {rB.profit_factor:<18.2f}")
    print(f"{'Expectancy em R':<28} | {rA.expectancy_r:<18.2f} | {rB.expectancy_r:<18.2f}")
    print(f"{'Max Drawdown (R)':<28} | {rA.max_dd_r:<18.1f} | {rB.max_dd_r:<18.1f}")
    print(f"{'OOS Profit Factor':<28} | {rA.oos.out_of_sample_pf:<18.2f} | {rB.oos.out_of_sample_pf:<18.2f}")
    print(f"{'Monte Carlo Prob Perda':<28} | {rA.monte_carlo.prob_net_loss:<18.1f}% | {rB.monte_carlo.prob_net_loss:<18.1f}%")
    print(f"{'Monte Carlo p95 MaxDD':<28} | {rA.monte_carlo.p95_max_dd_r:<18.1f}R | {rB.monte_carlo.p95_max_dd_r:<18.1f}R")
    print(f"{'Top 3 Concentração %':<28} | {rA.concentration.top3_pct:<18.1f}% | {rB.concentration.top3_pct:<18.1f}%")
    print(f"{'Net R sem Top 3':<28} | {rA.concentration.without_top3_net_r:<18.1f}R | {rB.concentration.without_top3_net_r:<18.1f}R")
    print(f"{'Estabilidade de Parâmetros':<28} | {rA.parameter_stability.parameter_stability_pct:<18.1f}% | {rB.parameter_stability.parameter_stability_pct:<18.1f}%")
    print(f"{'PF com Custos 2.0x':<28} | {rA.cost_sensitivity.cost_2x_pf:<18.2f} | {rB.cost_sensitivity.cost_2x_pf:<18.2f}")

    profiler.stop_timer("reporting_time")
    profiler.stop_timer("total_time")
    rep_dict = profiler.to_dict()

    print("\n==================================================")
    print("PERFORMANCE E PROFILING MEDIDO")
    print("==================================================")
    print(f"Tempo Total          : {rep_dict['total_time_sec']:.4f}s")
    print(f"Data Acquisition     : {rep_dict['data_acquisition_time_sec']:.4f}s")
    print(f"Stage 2 Backtest     : {rep_dict['backtest_time_sec']:.4f}s")
    print("==================================================")


if __name__ == "__main__":
    run_hdf_stage2_deep_robustness()
