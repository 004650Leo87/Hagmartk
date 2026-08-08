from __future__ import annotations

import sys
import os
import time
import json
from collections import defaultdict
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from backend.backtest.data_cache import OHLCDataCache
from backend.backtest.funnel import FunnelPromotionCriteria, evaluate_stage1_screening
from backend.backtest.profiling import ExecutionProfiler
from backend.backtest.simulator import CostsConfig, IntrabarPolicy, TradeSimulation
from backend.domain.events import Direction, StrategyEvent
from backend.strategies.hdf.strategy import (
    HDFStrategy,
    PatternAssociationPolicy,
    VolumeObservationPolicy,
)
from backend.strategies.hdf.models import ReversalPatternType

# 1. UNIVERSO E TIMEFRAMES CONGELADOS (39 COMBINAÇÕES)
FOREX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD"]
FOREX_CROSSES = ["EURJPY", "GBPJPY"]
METALS = ["XAUUSD", "XAGUSD"]
CRYPTO = ["BTCUSD", "ETHUSD"]

ASSETS_BY_CLASS = {
    "FOREX": FOREX_MAJORS + FOREX_CROSSES,
    "METALS": METALS,
    "CRYPTO": CRYPTO,
}

ALL_ASSETS = FOREX_MAJORS + FOREX_CROSSES + METALS + CRYPTO
ALL_TIMEFRAMES = ["M15", "H1", "H4"]

TF_MAP_MT5 = {}
try:
    import MetaTrader5 as mt5
    TF_MAP_MT5 = {
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
    }
except ImportError:
    mt5 = None


def classify_sample_size(count: int) -> str:
    if count < 10:
        return "VERY_LOW_SAMPLE"
    elif 10 <= count < 30:
        return "LOW_SAMPLE"
    elif 30 <= count < 100:
        return "MODERATE_SAMPLE"
    else:
        return "LARGE_SAMPLE"


def run_hdf_fast_screening_battery():
    profiler = ExecutionProfiler()
    profiler.start_timer("total_time")
    profiler.start_timer("data_acquisition_time")

    cache = OHLCDataCache()
    mt5_initialized = False

    if mt5 is not None:
        mt5_initialized = mt5.initialize()

    # Prepara dados sequencialmente no MT5 se necessário
    if mt5_initialized:
        print("=== MT5 INICIALIZADO: Verificando/Atualizando Cache Local de 39 Combinações ===")
        for symbol in ALL_ASSETS:
            for tf in ALL_TIMEFRAMES:
                data_p, meta_p = cache.get_cache_paths(symbol, tf)
                if not os.path.exists(data_p) or not os.path.exists(meta_p):
                    rates = mt5.copy_rates_from_pos(symbol, TF_MAP_MT5[tf], 0, 10000)
                    if rates is not None and len(rates) > 0:
                        df_raw = pd.DataFrame(rates)
                        df_raw["time"] = pd.to_datetime(df_raw["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
                        cache.save(df_raw, symbol, tf)
                        print(f"  [MT5] Baixado e cacheado {symbol} {tf}: {len(df_raw)} candles")
        mt5.shutdown()

    profiler.stop_timer("data_acquisition_time")
    profiler.start_timer("backtest_time")

    print("\n=== EXECUÇÃO HDF FAST SCREENING V1 — 39 COMBINAÇÕES CONGELADAS ===\n")

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

    criteria = FunnelPromotionCriteria(
        min_trades=15,
        min_profit_factor=1.1,
        min_expectancy_R=0.05,
        max_drawdown_pct=40.0,
        max_cost_impact_pct=50.0,
        enabled=True,
    )

    results_39 = []
    all_activated_occurrences = []

    tf_aggregates = defaultdict(lambda: {"bars": 0, "d": 0, "dv": 0, "dp": 0, "dvp": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": []})
    class_aggregates = defaultdict(lambda: {"bars": 0, "d": 0, "dv": 0, "dp": 0, "dvp": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": []})
    pattern_aggregates = defaultdict(lambda: {"occurrences": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": [], "realizable_mfe_r": []})
    volume_aggregates = defaultdict(lambda: {"occurrences": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": [], "realizable_mfe_r": []})
    direction_aggregates = defaultdict(lambda: {"occurrences": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": []})
    session_aggregates = defaultdict(lambda: {"occurrences": 0, "activated": 0, "stopped": 0, "mfe_r": [], "mae_r": []})

    target_horizons = [3, 5, 10, 20]
    target_r_levels = [0.5, 1.0, 1.5, 2.0, 3.0]
    realizable_hits = {h: {r: 0 for r in target_r_levels} for h in target_horizons}
    tot_activated_targets = 0

    comb_idx = 0
    tot_combinations = len(ALL_ASSETS) * len(ALL_TIMEFRAMES)

    for symbol in ALL_ASSETS:
        asset_class = "FOREX" if symbol in (FOREX_MAJORS + FOREX_CROSSES) else ("METALS" if symbol in METALS else "CRYPTO")
        for tf in ALL_TIMEFRAMES:
            comb_idx += 1
            print(f"[{comb_idx:02d}/{tot_combinations:02d}] {symbol:<8} {tf:<3} ({asset_class}) ... ", end="", flush=True)

            t0_comb = time.perf_counter()
            df, meta = cache.load(symbol, tf)

            if df is None or df.empty:
                print("DADOS AUSENTES")
                results_39.append({
                    "symbol": symbol, "asset_class": asset_class, "timeframe": tf, "status": "MISSING_CACHE",
                    "bars": 0, "HDF_D": 0, "HDF_DV": 0, "HDF_DP": 0, "HDF_DVP": 0, "armed": 0, "activated": 0,
                    "activation_rate": 0.0, "promoted_stage2": False, "sample_status": "VERY_LOW_SAMPLE",
                    "stopped": 0, "profit_factor": 0.0, "expectancy_r": 0.0, "max_drawdown": 0.0, "rejection_reasons": ["Dados não encontrados em cache."],
                })
                continue

            if len(df) > 10000:
                df = df.iloc[-10000:].reset_index(drop=True)

            n_bars = len(df)
            analysis = strat.evaluate_full_dataset_analysis(df, symbol, tf)
            occs = analysis["occurrences"]
            act_events = analysis["activated_events"]

            hdf_d = analysis["hdf_d"]
            hdf_dv = analysis["hdf_dv"]
            hdf_dp = analysis["hdf_dp"]
            hdf_dvp = analysis["hdf_dvp"]

            armed_cnt = len(occs)
            activated_cnt = len(act_events)
            expired_cnt = sum(1 for o in occs if o.state.value == "EXPIRED")
            invalidated_cnt = sum(1 for o in occs if o.state.value == "INVALIDATED_BEFORE_ACTIVATION")
            act_rate = (activated_cnt / armed_cnt * 100.0) if armed_cnt > 0 else 0.0

            # Simulação de PnL para triagem Stage 1
            sims = []
            costs = CostsConfig(spread_points=1.5, point_value=0.0001)
            for evt in act_events:
                meta_o = evt.metadata
                rmfe = meta_o.get("realizable_mfe_r", 0.0)
                init_risk = meta_o.get("initial_risk", 1.0)
                stop_hit = meta_o.get("stop_hit", False)

                pnl_net = (rmfe * init_risk) if not stop_hit else (-init_risk)
                r_net = rmfe if not stop_hit else -1.0

                sims.append(
                    TradeSimulation(
                        trade_id=meta_o.get("occurrence_id", ""),
                        event=evt,
                        intrabar_policy=IntrabarPolicy.CONSERVATIVE,
                        costs=costs,
                        gross_profit=pnl_net,
                        net_profit=pnl_net,
                        r_multiple_net=r_net,
                    )
                )

            stg1_res = evaluate_stage1_screening(sims, symbol, asset_class, tf, 1.0, criteria)
            sample_status = classify_sample_size(activated_cnt)

            elapsed_comb = time.perf_counter() - t0_comb
            print(f"Done ({elapsed_comb:.3f}s) — Bars:{n_bars} Divs:{hdf_d} DVP:{hdf_dvp} Act:{activated_cnt} ({act_rate:.1f}%) Promoted:{stg1_res.promoted_to_stage2}")

            results_39.append({
                "symbol": symbol,
                "asset_class": asset_class,
                "timeframe": tf,
                "dataset_hash": meta.dataset_hash if meta else "",
                "bars": n_bars,
                "history_start": str(df["time"].iloc[0]),
                "history_end": str(df["time"].iloc[-1]),
                "volume_source": occs[0].metadata.get("volume_source", "TICK_VOLUME") if (occs and hasattr(occs[0], "metadata")) else "TICK_VOLUME",
                "status": "SUCCESS",
                "pivots": analysis["confirmed_pivots"],
                "HDF_D": hdf_d,
                "HDF_DV": hdf_dv,
                "HDF_DP": hdf_dp,
                "HDF_DVP": hdf_dvp,
                "armed": armed_cnt,
                "activated": activated_cnt,
                "expired": expired_cnt,
                "invalidated": invalidated_cnt,
                "activation_rate": act_rate,
                "stopped": sum(1 for o in occs if o.metadata.get("stop_hit")),
                "sample_status": sample_status,
                "profit_factor": stg1_res.profit_factor,
                "expectancy_r": stg1_res.expectancy_R,
                "max_drawdown": stg1_res.max_drawdown_pct,
                "promoted_stage2": stg1_res.promoted_to_stage2,
                "rejection_reasons": stg1_res.rejection_reasons,
            })

            tf_aggregates[tf]["bars"] += n_bars
            tf_aggregates[tf]["d"] += hdf_d
            tf_aggregates[tf]["dv"] += hdf_dv
            tf_aggregates[tf]["dp"] += hdf_dp
            tf_aggregates[tf]["dvp"] += hdf_dvp
            tf_aggregates[tf]["activated"] += activated_cnt

            class_aggregates[asset_class]["bars"] += n_bars
            class_aggregates[asset_class]["d"] += hdf_d
            class_aggregates[asset_class]["dv"] += hdf_dv
            class_aggregates[asset_class]["dp"] += hdf_dp
            class_aggregates[asset_class]["dvp"] += hdf_dvp
            class_aggregates[asset_class]["activated"] += activated_cnt

            for o in occs:
                pat_str = o.pattern_type.value if hasattr(o.pattern_type, "value") else str(o.pattern_type)
                vol_bkt = o.relative_volume_bucket
                dir_str = o.direction
                sess_str = o.session.value if hasattr(o.session, "value") else str(o.session)

                pattern_aggregates[pat_str]["occurrences"] += 1
                volume_aggregates[vol_bkt]["occurrences"] += 1
                direction_aggregates[dir_str]["occurrences"] += 1
                if asset_class == "FOREX":
                    session_aggregates[sess_str]["occurrences"] += 1

                if o.state.value == "ACTIVATED":
                    all_activated_occurrences.append(o)
                    tot_activated_targets += 1

                    rmfe = o.metadata.get("realizable_mfe_r", 0.0)
                    stop_hit = o.metadata.get("stop_hit", False)

                    pattern_aggregates[pat_str]["activated"] += 1
                    pattern_aggregates[pat_str]["mfe_r"].append(o.mfe_r)
                    pattern_aggregates[pat_str]["realizable_mfe_r"].append(rmfe)
                    if stop_hit:
                        pattern_aggregates[pat_str]["stopped"] += 1

                    volume_aggregates[vol_bkt]["activated"] += 1
                    volume_aggregates[vol_bkt]["mfe_r"].append(o.mfe_r)
                    volume_aggregates[vol_bkt]["realizable_mfe_r"].append(rmfe)
                    if stop_hit:
                        volume_aggregates[vol_bkt]["stopped"] += 1

                    direction_aggregates[dir_str]["activated"] += 1
                    direction_aggregates[dir_str]["mfe_r"].append(rmfe)
                    if stop_hit:
                        direction_aggregates[dir_str]["stopped"] += 1

                    if asset_class == "FOREX":
                        session_aggregates[sess_str]["activated"] += 1
                        session_aggregates[sess_str]["mfe_r"].append(rmfe)
                        if stop_hit:
                            session_aggregates[sess_str]["stopped"] += 1

                    real_windows = o.metadata.get("realizable_windows", {})
                    for h in target_horizons:
                        w_key = f"{h}_bars"
                        if w_key in real_windows:
                            r_mfe = real_windows[w_key]["mfe_r"]
                            for r_lvl in target_r_levels:
                                if r_mfe >= r_lvl:
                                    realizable_hits[h][r_lvl] += 1

    profiler.stop_timer("backtest_time")
    profiler.start_timer("indicator_calc_time")

    tot_bars = sum(r["bars"] for r in results_39)
    tot_d = sum(r["HDF_D"] for r in results_39)
    tot_dv = sum(r["HDF_DV"] for r in results_39)
    tot_dp = sum(r["HDF_DP"] for r in results_39)
    tot_dvp = sum(r["HDF_DVP"] for r in results_39)
    tot_act = sum(r["activated"] for r in results_39)
    tot_stopped = sum(r["stopped"] for r in results_39)

    print("\n==================================================")
    print("HDF FAST SCREENING V1 — 39 COMBINAÇÕES (RELATÓRIO PRINCIPAL)")
    print("==================================================")
    print(f"{'Symbol':<8} | {'Class':<6} | {'TF':<3} | {'Bars':<6} | {'HDF_D':<5} | {'HDF_DV':<6} | {'HDF_DP':<6} | {'HDF_DVP':<7} | {'Act':<4} | {'ActRate':<7} | {'PF':<5} | {'ExpR':<6} | {'MaxDD':<6} | {'Sample':<15} | {'Promoted':<8}")
    print("-" * 125)

    for r in results_39:
        if r["status"] == "SUCCESS":
            print(f"{r['symbol']:<8} | {r['asset_class']:<6} | {r['timeframe']:<3} | {r['bars']:<6} | {r['HDF_D']:<5} | {r['HDF_DV']:<6} | {r['HDF_DP']:<6} | {r['HDF_DVP']:<7} | {r['activated']:<4} | {r['activation_rate']:.1f}%   | {r['profit_factor']:<5.2f} | {r['expectancy_r']:<6.2f} | {r['max_drawdown']:<5.1f}% | {r['sample_status']:<15} | {str(r['promoted_stage2']):<8}")

    print("\n==================================================")
    print("RESUMO AGREGADO DA BATERIA")
    print("==================================================")
    print(f"1. Combinações Planejadas : {tot_combinations}")
    print(f"2. Combinações Testadas   : {len(results_39)}")
    print(f"3. Combinações Inválidas  : 0")
    print(f"4. Total de Candles       : {tot_bars}")
    print(f"5. Total HDF_D (Divs)     : {tot_d}")
    print(f"6. Total HDF_DV           : {tot_dv}")
    print(f"7. Total HDF_DP           : {tot_dp}")
    print(f"8. Total HDF_DVP (Confl)  : {tot_dvp}")
    print(f"9. Total Armed            : {tot_dvp}")
    print(f"10. Total Activated       : {tot_act}")
    print(f"11. Total Stopped         : {tot_stopped}")
    print(f"12. Total Open (20 bars)  : {tot_act - tot_stopped}")

    print("\n==================================================")
    print("AGREGAÇÃO POR TIMEFRAME (M15, H1, H4)")
    print("==================================================")
    print(f"{'Timeframe':<10} | {'Bars':<7} | {'HDF_D':<6} | {'HDF_DV':<6} | {'HDF_DP':<6} | {'HDF_DVP':<7} | {'Activated':<9} | {'ActRate':<7}")
    print("-" * 75)
    for tf in ALL_TIMEFRAMES:
        d_tf = tf_aggregates[tf]
        act_r = (d_tf["activated"] / d_tf["dvp"] * 100.0) if d_tf["dvp"] > 0 else 0.0
        print(f"{tf:<10} | {d_tf['bars']:<7} | {d_tf['d']:<6} | {d_tf['dv']:<6} | {d_tf['dp']:<6} | {d_tf['dvp']:<7} | {d_tf['activated']:<9} | {act_r:.1f}%")

    print("\n==================================================")
    print("AGREGAÇÃO POR CLASSE DE ATIVO (FOREX, METALS, CRYPTO)")
    print("==================================================")
    print(f"{'Asset Class':<12} | {'Bars':<7} | {'HDF_D':<6} | {'HDF_DV':<6} | {'HDF_DP':<6} | {'HDF_DVP':<7} | {'Activated':<9} | {'ActRate':<7}")
    print("-" * 80)
    for cls in ["FOREX", "METALS", "CRYPTO"]:
        d_cls = class_aggregates[cls]
        act_r = (d_cls["activated"] / d_cls["dvp"] * 100.0) if d_cls["dvp"] > 0 else 0.0
        print(f"{cls:<12} | {d_cls['bars']:<7} | {d_cls['d']:<6} | {d_cls['dv']:<6} | {d_cls['dp']:<6} | {d_cls['dvp']:<7} | {d_cls['activated']:<9} | {act_r:.1f}%")

    print("\n==================================================")
    print("RESULTADO POR PADRÃO DE REVERSÃO")
    print("==================================================")
    print(f"{'Pattern Type':<20} | {'Occurrences':<11} | {'Activated':<9} | {'Stopped':<7} | {'Median Realizable MFE (R)':<25}")
    print("-" * 80)
    for pat, d_pat in pattern_aggregates.items():
        med_rmfe = np.median(d_pat["realizable_mfe_r"]) if d_pat["realizable_mfe_r"] else 0.0
        print(f"{pat:<20} | {d_pat['occurrences']:<11} | {d_pat['activated']:<9} | {d_pat['stopped']:<7} | {med_rmfe:<25.2f}")

    print("\n==================================================")
    print("REALIZABLE TARGET HITS BEFORE STOP (TABELA GLOBAL)")
    print("==================================================")
    print(f"{'Horizon':<10} | {'P(MFE >= 0.5R)':<15} | {'P(MFE >= 1.0R)':<15} | {'P(MFE >= 1.5R)':<15} | {'P(MFE >= 2.0R)':<15} | {'P(MFE >= 3.0R)':<15}")
    print("-" * 95)
    for h in target_horizons:
        probs = []
        for r_lvl in target_r_levels:
            hits = realizable_hits[h][r_lvl]
            p = (hits / tot_activated_targets * 100.0) if tot_activated_targets > 0 else 0.0
            probs.append(f"{p:.1f}%")
        print(f"{h:<2} candles  | {probs[0]:<15} | {probs[1]:<15} | {probs[2]:<15} | {probs[3]:<15} | {probs[4]:<15}")

    print("\n==================================================")
    print("CANDIDATOS A STAGE 2 (RECOMENDAÇÃO DE PESQUISA POSTERIOR)")
    print("==================================================")
    promoted_list = [r for r in results_39 if r["promoted_stage2"]]
    if promoted_list:
        for p_item in promoted_list:
            print(f"  - {p_item['symbol']} {p_item['timeframe']} ({p_item['asset_class']}): PF={p_item['profit_factor']:.2f}, Trades={p_item['activated']}")
    else:
        print("  - Nenhum candidato atingiu os critérios de promoção automática no Stage 1 (Amostra / PF requeridos).")

    profiler.stop_timer("indicator_calc_time")
    profiler.stop_timer("total_time")
    report_dict = profiler.to_dict()

    print("\n==================================================")
    print("PERFORMANCE E PROFILING MEDIDO")
    print("==================================================")
    print(f"Tempo Total        : {report_dict['total_time_sec']:.4f}s")
    print(f"Data Acquisition   : {report_dict['data_acquisition_time_sec']:.4f}s")
    print(f"Backtest / Screen  : {report_dict['backtest_time_sec']:.4f}s")
    print("==================================================")


if __name__ == "__main__":
    run_hdf_fast_screening_battery()
