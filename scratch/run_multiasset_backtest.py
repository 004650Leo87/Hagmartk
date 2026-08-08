from __future__ import annotations

import sys
import os
import json
import time
import math
from collections import defaultdict

sys.path.insert(0, os.path.abspath("."))

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from backend.backtest.laboratory import QuantitativeRobustnessLab
from backend.backtest.reconciliation import reconcile_backtest
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy

# ==============================================================
# CESTA MULTIATIVO APROVADA (congelada antes dos resultados)
# ==============================================================
BASKET = [
    {"symbol": "EURUSD",  "category": "FOREX",   "point_value": 0.0001, "spread_points": 2.0,  "slippage_points": 0.5},
    {"symbol": "GBPUSD",  "category": "FOREX",   "point_value": 0.0001, "spread_points": 2.0,  "slippage_points": 0.5},
    {"symbol": "USDJPY",  "category": "FOREX",   "point_value": 0.01,   "spread_points": 2.0,  "slippage_points": 0.5},
    {"symbol": "XAUUSD",  "category": "METALS",  "point_value": 0.01,   "spread_points": 25.0, "slippage_points": 5.0},
    {"symbol": "XAGUSD",  "category": "METALS",  "point_value": 0.001,  "spread_points": 50.0, "slippage_points": 10.0},
    {"symbol": "US500",   "category": "INDICES", "point_value": 0.01,   "spread_points": 50.0, "slippage_points": 10.0},
    {"symbol": "USTEC",   "category": "INDICES", "point_value": 0.01,   "spread_points": 50.0, "slippage_points": 10.0},
    {"symbol": "DE40",    "category": "INDICES", "point_value": 0.01,   "spread_points": 80.0, "slippage_points": 20.0},
    {"symbol": "BRENT",   "category": "ENERGY",  "point_value": 0.001,  "spread_points": 30.0, "slippage_points": 10.0},
    {"symbol": "BTCUSD",  "category": "CRYPTO",  "point_value": 0.01,   "spread_points": 500.0,"slippage_points": 100.0},
    {"symbol": "ETHUSD",  "category": "CRYPTO",  "point_value": 0.01,   "spread_points": 100.0,"slippage_points": 25.0},
]

TIMEFRAME = "D1"
MT5_TIMEFRAME = mt5.TIMEFRAME_D1
MAX_CANDLES = 10000
WARMUP = 80  # min warmup bars required after strategy warmup

# Reduced parameter grid for multi-asset (speed vs. single-asset full grid)
GRID_ENTRIES = [50, 55, 60]
GRID_EXITS = [15, 20, 25]
GRID_ATR = [20]
GRID_STOP = [2.0]


def log(msg: str):
    print(msg, flush=True)


def fetch_data(symbol: str) -> pd.DataFrame | None:
    rates = mt5.copy_rates_from_pos(symbol, MT5_TIMEFRAME, 0, MAX_CANDLES)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def validate_data(df: pd.DataFrame, symbol: str) -> tuple[bool, list[str]]:
    issues = []
    if df.isnull().any().any():
        issues.append("NaN values detected")
    if df.duplicated(subset=["time"]).any():
        issues.append("Duplicate timestamps")
    times = pd.to_datetime(df["time"])
    if not times.is_monotonic_increasing:
        issues.append("Non-chronological order")
    invalid_ohlc = df[
        (df["high"] < df["low"]) | (df["open"] <= 0) | (df["close"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0)
    ]
    if len(invalid_ohlc) > 0:
        issues.append(f"{len(invalid_ohlc)} bars with invalid OHLC")
    return (len(issues) == 0), issues


def compute_frequency_metrics(sims, history_years: float) -> dict:
    if not sims or history_years <= 0:
        return {}
    entry_dates = [s.entry_time[:10] for s in sims]
    n = len(sims)
    trades_per_year = n / history_years
    trades_per_month = trades_per_year / 12.0

    dates_sorted = sorted(entry_dates)
    if len(dates_sorted) > 1:
        date_objs = [pd.to_datetime(d) for d in dates_sorted]
        gaps = [(date_objs[i+1] - date_objs[i]).days for i in range(len(date_objs)-1)]
        avg_gap = float(np.mean(gaps))
        med_gap = float(np.median(gaps))
    else:
        avg_gap = 0.0
        med_gap = 0.0

    return {
        "total_trades": n,
        "history_years": round(history_years, 2),
        "trades_per_year": round(trades_per_year, 2),
        "trades_per_month": round(trades_per_month, 3),
        "average_days_between_entries": round(avg_gap, 1),
        "median_days_between_entries": round(med_gap, 1),
    }


def build_result_summary(symbol: str, category: str, report, freq: dict, df_years: float) -> dict:
    if report.status != "SUCCESS" or report.metrics_overall is None:
        return {
            "symbol": symbol, "category": category,
            "status": report.status,
            "classification": report.final_classification,
        }

    m = report.metrics_overall
    mc = report.monte_carlo
    conc = report.concentration
    pr = report.parameter_robustness
    wf = report.walk_forward
    ls = report.long_vs_short
    nm = report.new_metrics
    ca = report.component_audit

    sims_all = []  # Not accessible directly here — embedded in report

    long_pf = ls.get("LONG", {}).get("profit_factor", 0.0)
    short_pf = ls.get("SHORT", {}).get("profit_factor", 0.0)

    return {
        "symbol": symbol,
        "category": category,
        "history_years": round(df_years, 2),
        "trades": m.total_trades,
        "trades_per_year": freq.get("trades_per_year", 0),
        "net_result": round(m.net_result, 2),
        "profit_factor": round(m.profit_factor, 4),
        "win_rate": round(m.win_rate, 4),
        "expectancy_R": round(nm.get("average_R", 0.0), 4),
        "median_R": round(nm.get("median_R", 0.0), 4),
        "max_drawdown": round(m.max_drawdown, 2),
        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
        "walk_forward_status": "STABLE" if wf.stability_pass else "UNSTABLE",
        "monte_carlo_prob_loss_pct": round(mc.prob_final_loss_pct, 2),
        "top3_concentration_pct": round(conc.top_3_contribution_pct, 2),
        "parameter_stability_pct": round(pr.positive_combinations_pct, 2),
        "long_PF": round(long_pf, 4),
        "short_PF": round(short_pf, 4),
        "sample_size_status": ca.sample_size_classification if ca else "UNKNOWN",
        "concentration_risk": conc.concentration_risk,
        "robustness_classification": report.final_classification,
        "entry_dates": [],  # filled externally
    }


def run_portfolio():
    log("\n=== HAGMARTK — GENERALIZAÇÃO MULTIATIVO D1 ===")
    log(f"Cesta aprovada: {[b['symbol'] for b in BASKET]}\n")

    if not mt5.initialize():
        log(f"ERRO FATAL: MT5 não inicializou — {mt5.last_error()}")
        sys.exit(1)

    all_results = []
    all_sims_by_symbol = {}
    portfolio_entry_dates = []

    for idx, asset in enumerate(BASKET, 1):
        symbol = asset["symbol"]
        category = asset["category"]
        n_total = len(BASKET)

        log(f"\n[{idx}/{n_total}] {symbol} ({category}) — Fase B: baixando histórico completo...")
        t0 = time.time()

        df = fetch_data(symbol)
        if df is None:
            log(f"[{idx}/{n_total}] {symbol} — DATA_INSUFFICIENT (sem resposta MT5)")
            all_results.append({"symbol": symbol, "category": category, "status": "DATA_INSUFFICIENT", "classification": "ROBUSTNESS_NOT_EVALUABLE"})
            continue

        candle_count = len(df)
        t_first = df["time"].iloc[0]
        t_last = df["time"].iloc[-1]
        date_start = pd.to_datetime(t_first)
        date_end = pd.to_datetime(t_last)
        years = max(1.0, (date_end - date_start).days / 365.25)
        effective = max(0, candle_count - WARMUP)

        log(f"[{idx}/{n_total}] {symbol} — {candle_count} candles | {t_first[:10]} -> {t_last[:10]} | {years:.1f} anos | effective={effective}")

        # Validação de qualidade dos dados
        data_ok, issues = validate_data(df, symbol)
        if not data_ok:
            log(f"[{idx}/{n_total}] {symbol} — DATA_INVALID: {issues}")
            all_results.append({"symbol": symbol, "category": category, "status": "DATA_INVALID", "issues": issues, "classification": "ROBUSTNESS_NOT_EVALUABLE"})
            continue

        if effective < 30:
            log(f"[{idx}/{n_total}] {symbol} — DATA_INSUFFICIENT (apenas {effective} candles efetivos após warmup)")
            all_results.append({"symbol": symbol, "category": category, "status": "DATA_INSUFFICIENT", "classification": "ROBUSTNESS_NOT_EVALUABLE"})
            continue

        # Configuração de custos por ativo
        costs = CostsConfig(
            spread_points=asset["spread_points"],
            point_value=asset["point_value"],
            commission_per_trade=0.0,
            slippage_points=asset["slippage_points"],
            swap_per_bar=0.0,
        )

        log(f"[{idx}/{n_total}] {symbol} — Iniciando backtest (55/20/ATR20/2N)...")
        strategy = HagmartkTrendReferenceStrategy()

        lab = QuantitativeRobustnessLab(
            strategy=strategy,
            symbol=symbol,
            timeframe=TIMEFRAME,
            costs=costs,
            intrabar_policy=IntrabarPolicy.CONSERVATIVE,
        )

        try:
            report = lab.run_full_robustness_audit(
                df,
                run_parameter_grid=True,
                grid_entry_lookbacks=GRID_ENTRIES,
                grid_exit_lookbacks=GRID_EXITS,
                grid_atr_periods=GRID_ATR,
                grid_stop_multipliers=GRID_STOP,
                monte_carlo_sims=5000,
                monte_carlo_seed=42,
            )
        except Exception as err:
            log(f"[{idx}/{n_total}] {symbol} — ERRO no laboratório: {err}")
            all_results.append({"symbol": symbol, "category": category, "status": "ERROR", "error": str(err), "classification": "ROBUSTNESS_NOT_EVALUABLE"})
            continue

        trades_n = report.metrics_overall.total_trades if report.metrics_overall else 0
        log(f"[{idx}/{n_total}] {symbol} — backtest concluído — {trades_n} trades")
        log(f"[{idx}/{n_total}] {symbol} — robustness concluída — {report.final_classification}")

        # Frequência
        # Re-run engine quickly to get sims list for frequency/portfolio analysis
        engine_sims = []
        try:
            from backend.backtest.engine import BacktestEngine
            eng = BacktestEngine(strategy=HagmartkTrendReferenceStrategy(), intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=costs)
            exp = eng.run_experiment(df, symbol=symbol, timeframe=TIMEFRAME)
            engine_sims = exp.simulations
        except Exception:
            pass

        freq = compute_frequency_metrics(engine_sims, years)
        all_sims_by_symbol[symbol] = engine_sims

        # Coletar datas de entrada para análise de portfólio
        for s in engine_sims:
            portfolio_entry_dates.append({"symbol": symbol, "category": category, "date": s.entry_time[:10]})

        result = build_result_summary(symbol, category, report, freq, years)
        result.update({
            "first_candle": t_first[:10],
            "last_candle": t_last[:10],
            "candle_count": candle_count,
            "effective_candles": effective,
            "frequency": freq,
        })
        all_results.append(result)

        elapsed = time.time() - t0
        log(f"[{idx}/{n_total}] {symbol} — completo em {elapsed:.0f}s\n")

    mt5.shutdown()

    # ===============================================
    # ANÁLISE DE FREQUÊNCIA DE PORTFOLIO
    # ===============================================
    log("\n=== ANÁLISE DE FREQUÊNCIA DO PORTFOLIO ===")
    pdf = pd.DataFrame(portfolio_entry_dates)
    freq_report = {}
    if not pdf.empty:
        date_obj = pd.to_datetime(pdf["date"])
        all_dates_sorted = sorted(pdf["date"].unique())
        total_date_span_years = 0.0

        # Calcular pelo span total dos dados (máx data - mín data)
        try:
            t_min = pd.to_datetime(min(all_dates_sorted))
            t_max = pd.to_datetime(max(all_dates_sorted))
            total_date_span_years = max(1.0, (t_max - t_min).days / 365.25)
        except Exception:
            total_date_span_years = 1.0

        total_opps = len(pdf)
        opps_per_year = total_opps / total_date_span_years
        opps_per_month = opps_per_year / 12.0
        opps_per_week = opps_per_year / 52.0

        dates_with_opp = len(pdf["date"].unique())
        by_date = pdf.groupby("date")["symbol"].count()
        max_same_day = int(by_date.max())
        pct_simultaneous = float((by_date[by_date > 1].sum() / total_opps * 100.0)) if total_opps > 0 else 0.0

        # Ativos mais frequentemente simultâneos
        simultaneous_days = by_date[by_date > 1].index.tolist()
        co_occur = defaultdict(int)
        for d in simultaneous_days:
            syms = pdf[pdf["date"] == d]["symbol"].tolist()
            for i in range(len(syms)):
                for j in range(i+1, len(syms)):
                    pair = tuple(sorted([syms[i], syms[j]]))
                    co_occur[pair] += 1

        top_pairs = sorted(co_occur.items(), key=lambda x: -x[1])[:5]

        freq_report = {
            "total_opportunities": total_opps,
            "opportunities_per_year": round(opps_per_year, 1),
            "opportunities_per_month": round(opps_per_month, 2),
            "opportunities_per_week": round(opps_per_week, 2),
            "days_with_at_least_one_opportunity": dates_with_opp,
            "max_same_day_opportunities": max_same_day,
            "pct_simultaneous_events": round(pct_simultaneous, 1),
            "top_simultaneous_pairs": [{"pair": list(p[0]), "count": p[1]} for p in top_pairs],
        }

        log(f"Oportunidades totais: {total_opps}")
        log(f"Por ano: {opps_per_year:.1f} | Por mês: {opps_per_month:.2f} | Por semana: {opps_per_week:.2f}")
        log(f"Dias com ao menos 1 oportunidade: {dates_with_opp}")
        log(f"Máximo de oportunidades no mesmo dia: {max_same_day}")
        log(f"% de eventos simultâneos: {pct_simultaneous:.1f}%")

    # ===============================================
    # GENERALIZATION MATRIX
    # ===============================================
    valid_results = [r for r in all_results if r.get("status") not in ("DATA_INSUFFICIENT", "DATA_INVALID", "ERROR")]
    invalid_results = [r for r in all_results if r.get("status") in ("DATA_INSUFFICIENT", "DATA_INVALID", "ERROR")]

    log("\n=== GENERALIZATION MATRIX ===")
    log(f"{'Symbol':<10} {'Cat':<8} {'Yrs':<5} {'Trades':<7} {'T/Yr':<6} {'PF':<6} {'E(R)':<7} {'MedR':<7} {'DD_pct':<8} {'WF':<8} {'MC%':<6} {'Top3%':<7} {'ParStab%':<9} {'LongPF':<8} {'ShortPF':<8} {'SSize':<22} {'Class'}")
    for r in valid_results:
        log(f"{r.get('symbol',''):<10} {r.get('category',''):<8} {r.get('history_years',0):<5.1f} {r.get('trades',0):<7} {r.get('trades_per_year',0):<6.1f} {r.get('profit_factor',0):<6.3f} {r.get('expectancy_R',0):<7.4f} {r.get('median_R',0):<7.4f} {r.get('max_drawdown_pct',0):<8.2f} {r.get('walk_forward_status',''):<8} {r.get('monte_carlo_prob_loss_pct',0):<6.2f} {r.get('top3_concentration_pct',0):<7.1f} {r.get('parameter_stability_pct',0):<9.1f} {r.get('long_PF',0):<8.3f} {r.get('short_PF',0):<8.3f} {r.get('sample_size_status',''):<22} {r.get('robustness_classification','')}")

    # Métricas agregadas
    if valid_results:
        pfs = [r.get("profit_factor", 0.0) for r in valid_results if r.get("profit_factor", 0.0) > 0]
        exp_rs = [r.get("expectancy_R", 0.0) for r in valid_results]
        dd_pcts = [r.get("max_drawdown_pct", 0.0) for r in valid_results]
        top3s = [r.get("top3_concentration_pct", 0.0) for r in valid_results]

        log(f"\nMediana PF: {np.median(pfs):.4f}")
        log(f"Mediana Expectancy R: {np.median(exp_rs):.4f}")
        log(f"Mediana Drawdown%: {np.median(dd_pcts):.2f}%")
        log(f"Mediana Top3 Concentration: {np.median(top3s):.1f}%")

    # Classificações
    classifications = defaultdict(int)
    for r in all_results:
        classifications[r.get("robustness_classification", "ROBUSTNESS_NOT_EVALUABLE")] += 1
    log(f"\nClassificações: {dict(classifications)}")

    # Salvar resultado completo em JSON
    output = {
        "basket": [b["symbol"] for b in BASKET],
        "valid_count": len(valid_results),
        "invalid_count": len(invalid_results),
        "results": all_results,
        "portfolio_frequency": freq_report,
        "classifications": dict(classifications),
    }
    with open("scratch/multiasset_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    log("\nResultados completos salvos em scratch/multiasset_results.json")


if __name__ == "__main__":
    run_portfolio()
