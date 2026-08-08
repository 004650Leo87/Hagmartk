from __future__ import annotations

import sys
import os
import json
import time
import MetaTrader5 as mt5
import pandas as pd

sys.path.insert(0, os.path.abspath("."))

from backend.backtest.data_cache import OHLCDataCache
from backend.backtest.funnel import FunnelPromotionCriteria, evaluate_stage1_screening
from backend.backtest.laboratory import QuantitativeRobustnessLab
from backend.backtest.profiling import ExecutionProfiler
from backend.backtest.reconciliation import reconcile_backtest
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy

SAMPLE_COMBOS = [
    {"symbol": "EURUSD", "timeframe": "D1", "mt5_tf": mt5.TIMEFRAME_D1, "category": "FOREX", "spread": 2.0, "point": 0.0001, "slip": 0.5},
    {"symbol": "EURUSD", "timeframe": "H1", "mt5_tf": mt5.TIMEFRAME_H1, "category": "FOREX", "spread": 2.0, "point": 0.0001, "slip": 0.5},
    {"symbol": "XAUUSD", "timeframe": "D1", "mt5_tf": mt5.TIMEFRAME_D1, "category": "METALS", "spread": 25.0, "point": 0.01, "slip": 5.0},
    {"symbol": "BTCUSD", "timeframe": "D1", "mt5_tf": mt5.TIMEFRAME_D1, "category": "CRYPTO", "spread": 500.0, "point": 0.01, "slip": 100.0},
]


def run_benchmark():
    print("=== CONTROLLED PERFORMANCE BENCHMARK: OLD VS NEW FUNNEL ARCHITECTURE ===")

    if not mt5.initialize():
        print(f"Erro MT5: {mt5.last_error()}")
        sys.exit(1)

    cache = OHLCDataCache()
    datasets = {}

    # 1. Fase de Aquisição e Cache local
    for item in SAMPLE_COMBOS:
        sym = item["symbol"]
        tf = item["timeframe"]
        df, meta = cache.load(sym, tf)
        if df is None:
            rates = mt5.copy_rates_from_pos(sym, item["mt5_tf"], 0, 10000)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
                meta = cache.save(df, sym, tf)
        datasets[f"{sym}_{tf}"] = (df, meta)

    mt5.shutdown()

    # -------------------------------------------------------------
    # EXECUÇÃO 1: ARQUITEURA ANTIGA (Unificada Incondicional)
    # -------------------------------------------------------------
    print("\n--- 1. EXECUTANDO ARQUITETURA ANTIGA (Pesada Incondicional) ---")
    t0_old = time.perf_counter()
    old_results = {}

    for item in SAMPLE_COMBOS:
        sym = item["symbol"]
        tf = item["timeframe"]
        df, meta = datasets[f"{sym}_{tf}"]
        costs = CostsConfig(spread_points=item["spread"], point_value=item["point"], slippage_points=item["slip"])

        strat = HagmartkTrendReferenceStrategy()
        lab = QuantitativeRobustnessLab(strat, sym, tf, costs)
        report = lab.run_full_robustness_audit(
            df,
            run_parameter_grid=True,
            grid_entry_lookbacks=[50, 55, 60],
            grid_exit_lookbacks=[15, 20, 25],
            grid_atr_periods=[20],
            grid_stop_multipliers=[2.0],
            monte_carlo_sims=3000,
            monte_carlo_seed=42,
        )
        old_results[f"{sym}_{tf}"] = {
            "net_result": report.metrics_overall.net_result if report.metrics_overall else 0.0,
            "trades": report.metrics_overall.total_trades if report.metrics_overall else 0,
            "classification": report.final_classification,
        }

    t_old_total = time.perf_counter() - t0_old
    print(f"Tempo total Arquitetura Antiga: {t_old_total:.2f}s")

    # -------------------------------------------------------------
    # EXECUÇÃO 2: NOVA ARQUITETURA EM FUNIL (Stage 1 + Stage 2)
    # -------------------------------------------------------------
    print("\n--- 2. EXECUTANDO NOVA ARQUITETURA (Funil Stage 1 + Stage 2) ---")
    t0_new = time.perf_counter()
    criteria = FunnelPromotionCriteria(min_trades=30, min_profit_factor=1.05, enabled=True)

    stage1_results = {}
    stage2_results = {}

    t0_stage1 = time.perf_counter()
    for item in SAMPLE_COMBOS:
        sym = item["symbol"]
        tf = item["timeframe"]
        df, meta = datasets[f"{sym}_{tf}"]
        costs = CostsConfig(spread_points=item["spread"], point_value=item["point"], slippage_points=item["slip"])

        from backend.backtest.engine import BacktestEngine
        eng = BacktestEngine(HagmartkTrendReferenceStrategy(), intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=costs)
        exp = eng.run_experiment(df, sym, tf)

        date_start = pd.to_datetime(df["time"].iloc[0])
        date_end = pd.to_datetime(df["time"].iloc[-1])
        years = max(0.01, (date_end - date_start).days / 365.25)

        s1_res = evaluate_stage1_screening(exp.simulations, sym, item["category"], tf, years, criteria, meta.dataset_hash if meta else "")
        stage1_results[f"{sym}_{tf}"] = s1_res

    t_stage1 = time.perf_counter() - t0_stage1
    print(f"Tempo Stage 1 (Fast Screening das 4 combinações): {t_stage1:.4f}s")

    t0_stage2 = time.perf_counter()
    for item in SAMPLE_COMBOS:
        sym = item["symbol"]
        tf = item["timeframe"]
        key = f"{sym}_{tf}"
        s1 = stage1_results[key]

        if s1.promoted_to_stage2:
            print(f"  -> Promovido para Stage 2: {key}")
            df, meta = datasets[key]
            costs = CostsConfig(spread_points=item["spread"], point_value=item["point"], slippage_points=item["slip"])
            lab = QuantitativeRobustnessLab(HagmartkTrendReferenceStrategy(), sym, tf, costs)
            report = lab.run_full_robustness_audit(
                df,
                run_parameter_grid=True,
                grid_entry_lookbacks=[50, 55, 60],
                grid_exit_lookbacks=[15, 20, 25],
                grid_atr_periods=[20],
                grid_stop_multipliers=[2.0],
                monte_carlo_sims=3000,
                monte_carlo_seed=42,
            )
            stage2_results[key] = report
        else:
            print(f"  -- Rejeitado no Stage 1 (ignora Monte Carlo/WF): {key} — Motivos: {s1.rejection_reasons}")

    t_stage2 = time.perf_counter() - t0_stage2
    t_new_total = time.perf_counter() - t0_new
    speedup = t_old_total / t_new_total if t_new_total > 0 else 1.0

    print(f"\nTempo Stage 2 (Deep Robustness): {t_stage2:.2f}s")
    print(f"Tempo total Nova Arquitetura: {t_new_total:.2f}s")
    print(f"Speedup real medido na amostra: {speedup:.2f}x")

    # Verificação de Identidade Matemática
    print("\n=== VERIFICAÇÃO DE IDENTIDADE MATEMÁTICA ===")
    for key, old_item in old_results.items():
        s1 = stage1_results[key]
        print(f"Combinacao {key}:")
        print(f"  Antigo -> Trades: {old_item['trades']}, Net PnL: ${old_item['net_result']:.2f}")
        print(f"  Novo   -> Stage 1 Trades: {s1.total_trades}, Net PnL: ${s1.net_pnl:.2f}, Promovido: {s1.promoted_to_stage2}")


if __name__ == "__main__":
    run_benchmark()
