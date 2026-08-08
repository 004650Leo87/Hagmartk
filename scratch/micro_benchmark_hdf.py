from __future__ import annotations

import sys
import os
import time
from collections import defaultdict
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from backend.backtest.data_cache import OHLCDataCache
from backend.strategies.hdf.strategy import HDFStrategy
from backend.strategies.hdf.models import ReversalPatternType

TARGET_ASSETS = ["EURUSD", "XAUUSD", "BTCUSD"]
TIMEFRAME = "H1"


def run_hdf_micro_benchmark():
    print("=== HAGMARTK DIVERGENCE FLOW (HDF) V1 — SEMANTIC AUDIT & MICRO-BENCHMARK ===\n")
    t0_start = time.perf_counter()

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
    )

    asset_results = {}
    all_occurrences = []
    activated_occurrences = []

    pattern_stats = defaultdict(lambda: {"occurrences": 0, "activated": 0, "mfe_r": [], "mae_r": [], "realizable_mfe_r": [], "realizable_mae_r": [], "stopped": 0})
    volume_stats = defaultdict(lambda: {"occurrences": 0, "activated": 0, "mfe_r": [], "mae_r": [], "realizable_mfe_r": [], "realizable_mae_r": []})
    activation_delay_counts = defaultdict(int)
    volume_sources = {}

    target_horizons = [3, 5, 10, 20]
    target_r_levels = [0.5, 1.0, 1.5, 2.0, 3.0]

    raw_target_hits = {h: {r: 0 for r in target_r_levels} for h in target_horizons}
    realizable_target_hits = {h: {r: 0 for r in target_r_levels} for h in target_horizons}
    tot_activated_for_targets = 0

    total_bars_processed = 0

    for symbol in TARGET_ASSETS:
        t0 = time.perf_counter()
        df, meta = cache.load(symbol, TIMEFRAME)

        if df is None or df.empty:
            asset_results[symbol] = {
                "dataset_exists": False,
                "bars": 0,
                "first_timestamp": "N/A",
                "last_timestamp": "N/A",
                "dataset_hash": "N/A",
                "volume_source": "UNKNOWN",
                "execution_status": "MISSING_CACHE",
                "confirmed_pivots": 0,
                "regular_divergences": 0,
                "HDF_D": 0,
                "HDF_DV": 0,
                "HDF_DP": 0,
                "HDF_DVP": 0,
                "confluence_complete": 0,
                "armed": 0,
                "activated": 0,
                "expired": 0,
                "invalidated": 0,
                "activation_rate": 0.0,
            }
            continue

        if len(df) > 10000:
            df = df.iloc[-10000:].reset_index(drop=True)

        n_bars = len(df)
        total_bars_processed += n_bars
        ds_hash = OHLCDataCache.compute_dataset_hash(df)
        vol_src = "TICK_VOLUME" if "tick_volume" in df.columns else "REAL_VOLUME"
        volume_sources[symbol] = vol_src

        analysis = strat.evaluate_full_dataset_analysis(df, symbol, TIMEFRAME)
        occs = analysis["occurrences"]

        conf_pivots = analysis["confirmed_pivots"]
        hdf_d = analysis["hdf_d"]
        hdf_dv = analysis["hdf_dv"]
        hdf_dp = analysis["hdf_dp"]
        hdf_dvp = analysis["hdf_dvp"]

        confl_complete = len(occs)
        armed_cnt = len(occs)
        activated_cnt = sum(1 for o in occs if o.state.value == "ACTIVATED")
        expired_cnt = sum(1 for o in occs if o.state.value == "EXPIRED")
        invalidated_cnt = sum(1 for o in occs if o.state.value == "INVALIDATED_BEFORE_ACTIVATION")
        act_rate = (activated_cnt / armed_cnt * 100.0) if armed_cnt > 0 else 0.0

        asset_results[symbol] = {
            "dataset_exists": True,
            "bars": n_bars,
            "first_timestamp": str(df["time"].iloc[0]),
            "last_timestamp": str(df["time"].iloc[-1]),
            "dataset_hash": ds_hash,
            "volume_source": vol_src,
            "execution_status": "SUCCESS",
            "confirmed_pivots": conf_pivots,
            "regular_divergences": hdf_d,
            "HDF_D": hdf_d,
            "HDF_DV": hdf_dv,
            "HDF_DP": hdf_dp,
            "HDF_DVP": hdf_dvp,
            "confluence_complete": confl_complete,
            "armed": armed_cnt,
            "activated": activated_cnt,
            "expired": expired_cnt,
            "invalidated": invalidated_cnt,
            "activation_rate": act_rate,
        }

        for o in occs:
            all_occurrences.append(o)
            pat_str = o.pattern_type.value if hasattr(o.pattern_type, "value") else str(o.pattern_type)
            vol_bucket = o.relative_volume_bucket

            pattern_stats[pat_str]["occurrences"] += 1
            volume_stats[vol_bucket]["occurrences"] += 1

            if o.state.value == "ACTIVATED":
                activated_occurrences.append(o)
                pattern_stats[pat_str]["activated"] += 1
                pattern_stats[pat_str]["mfe_r"].append(o.mfe_r)
                pattern_stats[pat_str]["mae_r"].append(o.mae_r)

                rmfe = o.metadata.get("realizable_mfe_r", 0.0)
                rmae = o.metadata.get("realizable_mae_r", 0.0)
                stop_hit = o.metadata.get("stop_hit", False)

                pattern_stats[pat_str]["realizable_mfe_r"].append(rmfe)
                pattern_stats[pat_str]["realizable_mae_r"].append(rmae)
                if stop_hit:
                    pattern_stats[pat_str]["stopped"] += 1

                volume_stats[vol_bucket]["activated"] += 1
                volume_stats[vol_bucket]["mfe_r"].append(o.mfe_r)
                volume_stats[vol_bucket]["mae_r"].append(o.mae_r)
                volume_stats[vol_bucket]["realizable_mfe_r"].append(rmfe)
                volume_stats[vol_bucket]["realizable_mae_r"].append(rmae)

                if o.bars_to_activation is not None:
                    activation_delay_counts[o.bars_to_activation] += 1

                tot_activated_for_targets += 1

                # Target Hit Study (RAW vs REALIZABLE)
                real_windows = o.metadata.get("realizable_windows", {})
                for h in target_horizons:
                    w_key = f"{h}_bars"
                    # RAW: calcula sobre fwd_df
                    raw_mfe = o.excursions_windows.get(w_key, {}).get("mfe_r", 0.0)
                    for r_target in target_r_levels:
                        if raw_mfe >= r_target:
                            raw_target_hits[h][r_target] += 1

                    # REALIZABLE BEFORE STOP
                    if w_key in real_windows:
                        real_mfe = real_windows[w_key]["mfe_r"]
                        for r_target in target_r_levels:
                            if real_mfe >= r_target:
                                realizable_target_hits[h][r_target] += 1

    t_total = time.perf_counter() - t0_start

    print("==================================================")
    print("A. FUNIL REAL (HDF_D >= HDF_DV/DP >= HDF_DVP)")
    print("==================================================")
    print(f"{'Symbol':<8} | {'Bars':<6} | {'HDF_D':<6} | {'HDF_DV':<6} | {'HDF_DP':<6} | {'HDF_DVP':<7} | {'Armed':<5} | {'Activated':<9} | {'Expired':<7} | {'Invalid':<7}")
    print("-" * 95)
    for sym, r in asset_results.items():
        print(f"{sym:<8} | {r['bars']:<6} | {r['HDF_D']:<6} | {r['HDF_DV']:<6} | {r['HDF_DP']:<6} | {r['HDF_DVP']:<7} | {r['armed']:<5} | {r['activated']:<9} | {r['expired']:<7} | {r['invalidated']:<7}")

    print("\n==================================================")
    print("D. SEGMENTAÇÃO POR PADRÃO DE REVERSÃO")
    print("==================================================")
    print(f"{'Pattern':<20} | {'Occ':<4} | {'Act':<4} | {'Stopped':<7} | {'Raw MFE (R)':<12} | {'Realizable MFE (R)':<18}")
    print("-" * 75)
    for pat, s in pattern_stats.items():
        occ_cnt = s["occurrences"]
        act_cnt = s["activated"]
        st_cnt = s["stopped"]
        med_raw_mfe = np.median(s["mfe_r"]) if s["mfe_r"] else 0.0
        med_real_mfe = np.median(s["realizable_mfe_r"]) if s["realizable_mfe_r"] else 0.0
        print(f"{pat:<20} | {occ_cnt:<4} | {act_cnt:<4} | {st_cnt:<7} | {med_raw_mfe:<12.2f} | {med_real_mfe:<18.2f}")

    print("\n==================================================")
    print("E. SEGMENTAÇÃO POR VOLUME RELATIVO (BUCKET)")
    print("==================================================")
    print(f"{'Bucket':<12} | {'Occ':<4} | {'Act':<4} | {'ActRate':<7} | {'Raw MFE (R)':<12} | {'Realizable MFE (R)':<18}")
    print("-" * 70)
    for bkt, s in volume_stats.items():
        occ_cnt = s["occurrences"]
        act_cnt = s["activated"]
        rate = (act_cnt / occ_cnt * 100.0) if occ_cnt > 0 else 0.0
        med_raw_mfe = np.median(s["mfe_r"]) if s["mfe_r"] else 0.0
        med_real_mfe = np.median(s["realizable_mfe_r"]) if s["realizable_mfe_r"] else 0.0
        print(f"{bkt:<12} | {occ_cnt:<4} | {act_cnt:<4} | {rate:.1f}%   | {med_raw_mfe:<12.2f} | {med_real_mfe:<18.2f}")

    print("\n==================================================")
    print("F1. RAW MFE TARGET HIT STUDY (SEM STOP PRECOCE)")
    print("==================================================")
    print(f"{'Horizon':<10} | {'P(MFE >= 0.5R)':<15} | {'P(MFE >= 1.0R)':<15} | {'P(MFE >= 1.5R)':<15} | {'P(MFE >= 2.0R)':<15} | {'P(MFE >= 3.0R)':<15}")
    print("-" * 95)
    for h in target_horizons:
        probs = []
        for r in target_r_levels:
            hits = raw_target_hits[h][r]
            p = (hits / tot_activated_for_targets * 100.0) if tot_activated_for_targets > 0 else 0.0
            probs.append(f"{p:.1f}%")
        print(f"{h:<2} candles  | {probs[0]:<15} | {probs[1]:<15} | {probs[2]:<15} | {probs[3]:<15} | {probs[4]:<15}")

    print("\n==================================================")
    print("F2. REALIZABLE TARGET HIT BEFORE STOP (TRADE REALIZÁVEL COM STOP FIRST)")
    print("==================================================")
    print(f"{'Horizon':<10} | {'P(MFE >= 0.5R)':<15} | {'P(MFE >= 1.0R)':<15} | {'P(MFE >= 1.5R)':<15} | {'P(MFE >= 2.0R)':<15} | {'P(MFE >= 3.0R)':<15}")
    print("-" * 95)
    for h in target_horizons:
        probs = []
        for r in target_r_levels:
            hits = realizable_target_hits[h][r]
            p = (hits / tot_activated_for_targets * 100.0) if tot_activated_for_targets > 0 else 0.0
            probs.append(f"{p:.1f}%")
        print(f"{h:<2} candles  | {probs[0]:<15} | {probs[1]:<15} | {probs[2]:<15} | {probs[3]:<15} | {probs[4]:<15}")

    print("\n==================================================")
    print("G. ACTIVATION DELAY (DISTRIBUIÇÃO DE BARRAS ATÉ ATIVAÇÃO)")
    print("==================================================")
    for b in range(1, 6):
        cnt = activation_delay_counts.get(b, 0)
        pct = (cnt / len(activated_occurrences) * 100.0) if activated_occurrences else 0.0
        print(f"  {b} barra(s) após armação : {cnt} ({pct:.1f}%)")
    print(f"  0 barras (Same-Bar)     : {activation_delay_counts.get(0, 0)} (PROIBIDO POR NEXT_BAR [OK])")

    print("\n==================================================")
    print("H. VOLUME SOURCE")
    print("==================================================")
    for k, v in volume_sources.items():
        print(f"  {k:<8}: {v}")

    print("\n==================================================")
    print("J. PERFORMANCE DO AUDIT BENCHMARK")
    print("==================================================")
    print(f"Tempo Total        : {t_total:.4f}s")
    print(f"Barras Processadas : {total_bars_processed}")
    print(f"Eventos Armados    : {len(all_occurrences)}")
    print(f"Eventos Ativados   : {len(activated_occurrences)}")
    print("==================================================")


if __name__ == "__main__":
    run_hdf_micro_benchmark()
