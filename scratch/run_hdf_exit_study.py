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
from backend.strategies.hdf.strategy import HDFStrategy, PatternAssociationPolicy, VolumeObservationPolicy

FOREX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
FOREX_CROSSES = ["EURJPY", "GBPJPY"]
METALS = ["XAUUSD", "XAGUSD"]
CRYPTO = ["BTCUSD", "ETHUSD"]

ALL_ASSETS = FOREX_MAJORS + FOREX_CROSSES + METALS + CRYPTO
ALL_TIMEFRAMES = ["M15", "H1", "H4"]

POLICIES_TO_STUDY = [
    # Fixed Target
    ExitPolicyConfig("EXIT_0_5R", ExitPolicyType.FIXED_TARGET, target_r=0.5),
    ExitPolicyConfig("EXIT_0_75R", ExitPolicyType.FIXED_TARGET, target_r=0.75),
    ExitPolicyConfig("EXIT_1R", ExitPolicyType.FIXED_TARGET, target_r=1.0),
    ExitPolicyConfig("EXIT_1_5R", ExitPolicyType.FIXED_TARGET, target_r=1.5),
    ExitPolicyConfig("EXIT_2R", ExitPolicyType.FIXED_TARGET, target_r=2.0),
    ExitPolicyConfig("EXIT_3R", ExitPolicyType.FIXED_TARGET, target_r=3.0),
    # Partial Runner
    ExitPolicyConfig("P50_0_5R_RUNNER", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=0.5, runner_target_r=2.0),
    ExitPolicyConfig("P50_1R_RUNNER", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=1.0, runner_target_r=2.0),
    ExitPolicyConfig("P50_1R_RUNNER_3R", ExitPolicyType.PARTIAL_RUNNER, partial_pct=0.5, partial_target_r=1.0, runner_target_r=3.0),
    # Time Exit
    ExitPolicyConfig("TIME_EXIT_5", ExitPolicyType.TIME_EXIT, time_horizon_bars=5),
    ExitPolicyConfig("TIME_EXIT_10", ExitPolicyType.TIME_EXIT, time_horizon_bars=10),
    ExitPolicyConfig("TIME_EXIT_20", ExitPolicyType.TIME_EXIT, time_horizon_bars=20),
]


def run_hdf_exit_policy_study():
    profiler = ExecutionProfiler()
    profiler.start_timer("total_time")
    profiler.start_timer("data_acquisition_time")

    cache = OHLCDataCache()
    strat = HDFStrategy(
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

    all_activated_records = []  # Tuplas (occ, fwd_df)

    tot_comb_d = 0
    tot_comb_dv = 0
    tot_comb_dp = 0
    tot_comb_dvp = 0
    tot_bars = 0

    comb_summary = []

    for symbol in ALL_ASSETS:
        for tf in ALL_TIMEFRAMES:
            df, meta = cache.load(symbol, tf)
            if df is None or df.empty:
                continue
            if len(df) > 10000:
                df = df.iloc[-10000:].reset_index(drop=True)

            tot_bars += len(df)
            analysis = strat.evaluate_full_dataset_analysis(df, symbol, tf)
            occs = analysis["occurrences"]

            d_cnt = analysis["hdf_d"]
            dv_cnt = analysis["hdf_dv"]
            dp_cnt = analysis["hdf_dp"]
            dvp_cnt = analysis["hdf_dvp"]

            tot_comb_d += d_cnt
            tot_comb_dv += dv_cnt
            tot_comb_dp += dp_cnt
            tot_comb_dvp += dvp_cnt

            comb_summary.append({
                "symbol": symbol, "tf": tf, "d": d_cnt, "dv": dv_cnt, "dp": dp_cnt, "dvp": dvp_cnt,
            })

            # Extrai sequência futura de candles para cada ocorrência ACTIVATED
            for occ in occs:
                if occ.state.value == "ACTIVATED":
                    act_idx = occ.metadata.get("activation_bar_index")
                    if act_idx is not None and act_idx < len(df) - 1:
                        fwd_df = df.iloc[act_idx + 1 : min(act_idx + 21, len(df))].reset_index(drop=True)
                    else:
                        fwd_df = pd.DataFrame()
                    all_activated_records.append((occ, fwd_df))

    profiler.stop_timer("data_acquisition_time")
    profiler.start_timer("backtest_time")

    tot_activated = len(all_activated_records)
    print(f"=== HDF EXIT POLICY STUDY V1 — 39 COMBINAÇÕES (417 ACTIVATED EVENTS RECONCILIADOS) ===")
    print(f"Total Activated Events Reconciliados: {tot_activated}")
    print(f"Total Candles Processados            : {tot_bars}\n")

    # 1. AUDITORIA DE CORREÇÃO DO HAMMER
    hammer_occurrences = [occ for occ, _ in all_activated_records if (occ.pattern_type.value if hasattr(occ.pattern_type, "value") else str(occ.pattern_type)) == "HAMMER"]
    hammer_realizable_mfes = [occ.metadata.get("realizable_mfe_r", 0.0) for occ in hammer_occurrences]
    hammer_median_correct = float(np.median(hammer_realizable_mfes)) if hammer_realizable_mfes else 0.0

    print("==================================================")
    print("A. CORREÇÃO DA INCONSISTÊNCIA DO HAMMER")
    print("==================================================")
    print(f"Número de trades ativados do tipo HAMMER no universo de 390.000 candles : {len(hammer_occurrences)}")
    print(f"Realizable MFE Mediano do HAMMER correto (Bateria 390k)                : {hammer_median_correct:.2f} R")
    print("Obs: O valor 3.03R pertencia ao micro-benchmark sintético anterior ( amostragem de 30k candles ).")

    # 2. STATUS OPEN AT HORIZON END
    stopped_in_20 = sum(1 for occ, _ in all_activated_records if occ.metadata.get("stop_hit"))
    open_at_20 = tot_activated - stopped_in_20

    open_reach_0_5r = 0
    open_reach_1r = 0
    open_reach_1_5r = 0
    open_reach_2r = 0
    open_reach_3r = 0

    for occ, _ in all_activated_records:
        if not occ.metadata.get("stop_hit"):
            rw = occ.metadata.get("realizable_windows", {})
            w20_mfe = rw.get("20_bars", {}).get("mfe_r", 0.0)
            if w20_mfe >= 0.5: open_reach_0_5r += 1
            if w20_mfe >= 1.0: open_reach_1r += 1
            if w20_mfe >= 1.5: open_reach_1_5r += 1
            if w20_mfe >= 2.0: open_reach_2r += 1
            if w20_mfe >= 3.0: open_reach_3r += 1

    print("\n==================================================")
    print("B. STATUS OPEN AT HORIZON END (20 BARRAS)")
    print("==================================================")
    print(f"Total Activated        : {tot_activated}")
    print(f"STOPPED (Stop Hit)     : {stopped_in_20} ({stopped_in_20/tot_activated*100:.1f}%)")
    print(f"OPEN_AT_HORIZON_END    : {open_at_20} ({open_at_20/tot_activated*100:.1f}%)")
    print("Dos 165 trades ABERTOS ao final de 20 barras:")
    print(f"  - Atingiram >= 0.5R antes da barra 20 : {open_reach_0_5r} ({open_reach_0_5r/open_at_20*100:.1f}%)")
    print(f"  - Atingiram >= 1.0R antes da barra 20 : {open_reach_1r} ({open_reach_1r/open_at_20*100:.1f}%)")
    print(f"  - Atingiram >= 1.5R antes da barra 20 : {open_reach_1_5r} ({open_reach_1_5r/open_at_20*100:.1f}%)")
    print(f"  - Atingiram >= 2.0R antes da barra 20 : {open_reach_2r} ({open_reach_2r/open_at_20*100:.1f}%)")
    print(f"  - Atingiram >= 3.0R antes da barra 20 : {open_reach_3r} ({open_reach_3r/open_at_20*100:.1f}%)")

    # 3. SIMULAÇÃO DAS POLÍTICAS DE SAÍDA
    policy_results = {}
    policy_metrics = {}

    for cfg in POLICIES_TO_STUDY:
        results_list = []
        for occ, fwd_df in all_activated_records:
            t_res = simulate_exit_policy_on_occurrence(occ, fwd_df, cfg, cost_per_trade_r=0.03)
            results_list.append(t_res)
        policy_results[cfg.name] = results_list
        policy_metrics[cfg.name] = calculate_exit_policy_metrics(results_list, cfg.name)

    print("\n==================================================")
    print("C. ESTUDO COMPARATIVO DE POLÍTICAS DE SAÍDA (GLOBAL)")
    print("==================================================")
    print(f"{'Policy':<18} | {'Trades':<6} | {'WinRate':<7} | {'Gross R':<8} | {'Net R':<8} | {'Exp R':<6} | {'Med R':<6} | {'PF':<5} | {'Payoff':<6} | {'MaxDD R':<7} | {'StopRate':<8} | {'CrossScore':<10}")
    print("-" * 125)

    for cfg in POLICIES_TO_STUDY:
        m = policy_metrics[cfg.name]
        print(f"{m.policy_name:<18} | {m.total_trades:<6} | {m.win_rate:5.1f}%   | {m.gross_r:<8.1f} | {m.net_r:<8.1f} | {m.expectancy_r:<6.2f} | {m.median_r:<6.2f} | {m.profit_factor_r:<5.2f} | {m.payoff_ratio:<6.2f} | {m.max_drawdown_r:<7.1f} | {m.stop_rate:6.1f}%   | {m.cross_context_score}/9")

    # 4. ANÁLISE POR TIMEFRAME
    print("\n==================================================")
    print("D. ESTUDO DE POLÍTICAS DE SAÍDA POR TIMEFRAME")
    print("==================================================")
    print(f"{'Policy':<18} | {'M15 Net R':<10} | {'M15 PF':<6} | {'H1 Net R':<10} | {'H1 PF':<6} | {'H4 Net R':<10} | {'H4 PF':<6}")
    print("-" * 80)
    for cfg in POLICIES_TO_STUDY:
        res_list = policy_results[cfg.name]
        m15_res = [r for r in res_list if r.timeframe == "M15"]
        h1_res = [r for r in res_list if r.timeframe == "H1"]
        h4_res = [r for r in res_list if r.timeframe == "H4"]

        m_m15 = calculate_exit_policy_metrics(m15_res, cfg.name)
        m_h1 = calculate_exit_policy_metrics(h1_res, cfg.name)
        m_h4 = calculate_exit_policy_metrics(h4_res, cfg.name)

        print(f"{cfg.name:<18} | {m_m15.net_r:<10.1f} | {m_m15.profit_factor_r:<6.2f} | {m_h1.net_r:<10.1f} | {m_h1.profit_factor_r:<6.2f} | {m_h4.net_r:<10.1f} | {m_h4.profit_factor_r:<6.2f}")

    # 5. ANÁLISE POR CLASSE DE ATIVO
    print("\n==================================================")
    print("E. ESTUDO DE POLÍTICAS DE SAÍDA POR CLASSE DE ATIVO")
    print("==================================================")
    print(f"{'Policy':<18} | {'Forex Net R':<11} | {'Forex PF':<8} | {'Metals Net R':<12} | {'Metals PF':<9} | {'Crypto Net R':<12} | {'Crypto PF':<9}")
    print("-" * 95)
    for cfg in POLICIES_TO_STUDY:
        res_list = policy_results[cfg.name]
        fx_res = [r for r in res_list if r.asset_class == "FOREX"]
        met_res = [r for r in res_list if r.asset_class == "METALS"]
        cry_res = [r for r in res_list if r.asset_class == "CRYPTO"]

        m_fx = calculate_exit_policy_metrics(fx_res, cfg.name)
        m_met = calculate_exit_policy_metrics(met_res, cfg.name)
        m_cry = calculate_exit_policy_metrics(cry_res, cfg.name)

        print(f"{cfg.name:<18} | {m_fx.net_r:<11.1f} | {m_fx.profit_factor_r:<8.2f} | {m_met.net_r:<12.1f} | {m_met.profit_factor_r:<9.2f} | {m_cry.net_r:<12.1f} | {m_cry.profit_factor_r:<9.2f}")

    # 6. ANÁLISE POR PADRÃO DE REVERSÃO
    print("\n==================================================")
    print("F. ESTUDO DE POLÍTICAS DE SAÍDA POR PADRÃO DE REVERSÃO")
    print("==================================================")
    print(f"{'Policy':<18} | {'BullEng Net R':<13} | {'BearEng Net R':<13} | {'ShootStar Net R':<15} | {'Hammer Net R':<12}")
    print("-" * 80)
    for cfg in POLICIES_TO_STUDY:
        res_list = policy_results[cfg.name]
        beng_res = [r for r in res_list if r.pattern_type == "BULLISH_ENGULFING"]
        reng_res = [r for r in res_list if r.pattern_type == "BEARISH_ENGULFING"]
        star_res = [r for r in res_list if r.pattern_type == "SHOOTING_STAR"]
        ham_res = [r for r in res_list if r.pattern_type == "HAMMER"]

        m_beng = calculate_exit_policy_metrics(beng_res, cfg.name)
        m_reng = calculate_exit_policy_metrics(reng_res, cfg.name)
        m_star = calculate_exit_policy_metrics(star_res, cfg.name)
        m_ham = calculate_exit_policy_metrics(ham_res, cfg.name)

        print(f"{cfg.name:<18} | {m_beng.net_r:<13.1f} | {m_reng.net_r:<13.1f} | {m_star.net_r:<15.1f} | {m_ham.net_r:<12.1f}")

    profiler.stop_timer("backtest_time")
    profiler.stop_timer("total_time")
    rep_dict = profiler.to_dict()

    print("\n==================================================")
    print("PERFORMANCE E PROFILING MEDIDO")
    print("==================================================")
    print(f"Tempo Total        : {rep_dict['total_time_sec']:.4f}s")
    print(f"Data Acquisition   : {rep_dict['data_acquisition_time_sec']:.4f}s")
    print(f"Exit Study Screen  : {rep_dict['backtest_time_sec']:.4f}s")
    print("==================================================")


if __name__ == "__main__":
    run_hdf_exit_policy_study()
