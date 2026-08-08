from __future__ import annotations

import sys
import os
import json
import time
import argparse
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
# CONFIGURAÇÃO CONGELADA DE ATIVOS E TIMEFRAMES
# ==============================================================
BASKET_ASSETS = [
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

TIMEFRAMES = [
    {"tf_str": "M15", "mt5_tf": mt5.TIMEFRAME_M15, "mins": 15},
    {"tf_str": "H1",  "mt5_tf": mt5.TIMEFRAME_H1,  "mins": 60},
    {"tf_str": "H4",  "mt5_tf": mt5.TIMEFRAME_H4,  "mins": 240},
    {"tf_str": "D1",  "mt5_tf": mt5.TIMEFRAME_D1,  "mins": 1440},
]

MAX_CANDLES = 10000
WARMUP = 80
CHECKPOINT_FILE = "scratch/multiasset_multitimeframe_checkpoint.json"
FINAL_RESULTS_FILE = "scratch/multiasset_multitimeframe_results.json"

GRID_ENTRIES = [50, 55, 60]
GRID_EXITS = [15, 20, 25]
GRID_ATR = [20]
GRID_STOP = [2.0]

def log(msg: str):
    print(msg, flush=True)

def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_checkpoint(data: dict):
    os.makedirs("scratch", exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def fetch_data(symbol: str, mt5_tf: int) -> pd.DataFrame | None:
    rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, MAX_CANDLES)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df

def validate_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
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

def compute_frequency_and_duration_metrics(sims, history_years: float, tf_mins: int) -> dict:
    if not sims or history_years <= 0:
        return {
            "total_trades": 0, "history_years": round(history_years, 2),
            "trades_per_year": 0.0, "trades_per_month": 0.0, "trades_per_week": 0.0,
            "average_time_between_entries_days": 0.0, "median_time_between_entries_days": 0.0,
            "average_trade_duration_bars": 0.0, "median_trade_duration_bars": 0.0,
            "average_trade_duration_hours": 0.0, "median_trade_duration_hours": 0.0,
        }
    n = len(sims)
    trades_per_year = n / history_years
    trades_per_month = trades_per_year / 12.0
    trades_per_week = trades_per_year / 52.0

    entry_dates = [pd.to_datetime(s.entry_time) for s in sims]
    entry_dates_sorted = sorted(entry_dates)
    if len(entry_dates_sorted) > 1:
        gaps_days = [(entry_dates_sorted[i+1] - entry_dates_sorted[i]).total_seconds() / 86400.0 for i in range(len(entry_dates_sorted)-1)]
        avg_gap_days = float(np.mean(gaps_days))
        med_gap_days = float(np.median(gaps_days))
    else:
        avg_gap_days = 0.0
        med_gap_days = 0.0

    durations_bars = [s.duration_bars for s in sims]
    avg_dur_bars = float(np.mean(durations_bars))
    med_dur_bars = float(np.median(durations_bars))

    # Converte duração em horas baseado no timeframe em minutos
    hours_per_bar = tf_mins / 60.0
    avg_dur_hours = avg_dur_bars * hours_per_bar
    med_dur_hours = med_dur_bars * hours_per_bar

    return {
        "total_trades": n,
        "history_years": round(history_years, 2),
        "trades_per_year": round(trades_per_year, 2),
        "trades_per_month": round(trades_per_month, 2),
        "trades_per_week": round(trades_per_week, 2),
        "average_time_between_entries_days": round(avg_gap_days, 2),
        "median_time_between_entries_days": round(med_gap_days, 2),
        "average_trade_duration_bars": round(avg_dur_bars, 1),
        "median_trade_duration_bars": round(med_dur_bars, 1),
        "average_trade_duration_hours": round(avg_dur_hours, 1),
        "median_trade_duration_hours": round(med_dur_hours, 1),
    }

def run_experiment():
    log("\n=== HAGMARTK — GENERALIZAÇÃO MULTIATIVO E MULTITIMEFRAME (44 COMBINAÇÕES) ===")

    # Construir lista teórica de 44 combinações
    combos = []
    for asset in BASKET_ASSETS:
        for tf_info in TIMEFRAMES:
            combos.append({
                "combo_key": f"{asset['symbol']}_{tf_info['tf_str']}",
                "asset": asset,
                "tf_info": tf_info,
            })

    n_total = len(combos)
    log(f"Total de combinações planejadas: {n_total}\n")

    checkpoint_data = load_checkpoint()
    log(f"Checkpoint carregado: {len(checkpoint_data)} combinações já concluídas anteriormente.")

    if not mt5.initialize():
        log(f"ERRO FATAL: MT5 não inicializou — {mt5.last_error()}")
        sys.exit(1)

    for idx, combo in enumerate(combos, 1):
        combo_key = combo["combo_key"]
        asset = combo["asset"]
        tf_info = combo["tf_info"]
        symbol = asset["symbol"]
        tf_str = tf_info["tf_str"]
        category = asset["category"]

        if combo_key in checkpoint_data:
            log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — já concluído no checkpoint (skipping).")
            continue

        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} ({category}) — buscando histórico no MT5...")
        t0 = time.time()

        df = fetch_data(symbol, tf_info["mt5_tf"])
        if df is None:
            log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — DATA_INSUFFICIENT (sem resposta MT5)")
            checkpoint_data[combo_key] = {
                "combo_key": combo_key, "symbol": symbol, "category": category, "timeframe": tf_str,
                "status": "DATA_INSUFFICIENT", "robustness_classification": "ROBUSTNESS_NOT_EVALUABLE",
            }
            save_checkpoint(checkpoint_data)
            continue

        candle_count = len(df)
        t_first = df["time"].iloc[0]
        t_last = df["time"].iloc[-1]
        date_start = pd.to_datetime(t_first)
        date_end = pd.to_datetime(t_last)
        history_days = max(1.0, (date_end - date_start).total_seconds() / 86400.0)
        history_years = max(0.01, history_days / 365.25)
        effective = max(0, candle_count - WARMUP)

        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — {candle_count} candles carregados | {t_first[:10]} -> {t_last[:10]} | {history_years:.2f} anos | efetivos={effective}")

        data_ok, issues = validate_data(df)
        if not data_ok:
            log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — DATA_INVALID: {issues}")
            checkpoint_data[combo_key] = {
                "combo_key": combo_key, "symbol": symbol, "category": category, "timeframe": tf_str,
                "status": "DATA_INVALID", "issues": issues, "robustness_classification": "ROBUSTNESS_NOT_EVALUABLE",
            }
            save_checkpoint(checkpoint_data)
            continue

        if effective < 30:
            log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — DATA_INSUFFICIENT (apenas {effective} candles efetivos após warmup)")
            checkpoint_data[combo_key] = {
                "combo_key": combo_key, "symbol": symbol, "category": category, "timeframe": tf_str,
                "status": "DATA_INSUFFICIENT", "robustness_classification": "ROBUSTNESS_NOT_EVALUABLE",
            }
            save_checkpoint(checkpoint_data)
            continue

        costs = CostsConfig(
            spread_points=asset["spread_points"],
            point_value=asset["point_value"],
            commission_per_trade=0.0,
            slippage_points=asset["slippage_points"],
            swap_per_bar=0.0,
        )

        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — backtest...")
        strategy = HagmartkTrendReferenceStrategy()
        lab = QuantitativeRobustnessLab(
            strategy=strategy,
            symbol=symbol,
            timeframe=tf_str,
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
                monte_carlo_sims=3000,
                monte_carlo_seed=42,
            )
        except Exception as err:
            log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — ERRO no laboratório: {err}")
            checkpoint_data[combo_key] = {
                "combo_key": combo_key, "symbol": symbol, "category": category, "timeframe": tf_str,
                "status": "ERROR", "error": str(err), "robustness_classification": "ROBUSTNESS_NOT_EVALUABLE",
            }
            save_checkpoint(checkpoint_data)
            continue

        m = report.metrics_overall
        trades_n = m.total_trades if m else 0
        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — {trades_n} trades encontrados")
        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — robustness concluída ({report.final_classification})")

        # Re-run engine to extract trade simulations for costs & frequency details
        from backend.backtest.engine import BacktestEngine
        eng = BacktestEngine(strategy=HagmartkTrendReferenceStrategy(), intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=costs)
        exp = eng.run_experiment(df, symbol=symbol, timeframe=tf_str)
        sims = exp.simulations

        freq = compute_frequency_and_duration_metrics(sims, history_years, tf_info["mins"])

        # Cálculo de Impacto de Custos
        total_costs = sum(
            (s.costs.slippage_points * s.costs.point_value) + (s.costs.spread_points * s.costs.point_value) for s in sims
        )
        gross_pnl = sum(s.gross_profit for s in sims)
        net_pnl = m.net_result if m else 0.0

        initial_risks = [s.initial_risk for s in sims if s.initial_risk > 0]
        avg_risk = float(np.mean(initial_risks)) if initial_risks else 1.0
        gross_R = float(gross_pnl / avg_risk) if avg_risk > 0 else 0.0
        net_R = float(net_pnl / avg_risk) if avg_risk > 0 else 0.0

        if gross_pnl > 0:
            cost_impact_pct = float((total_costs / gross_pnl) * 100.0)
        elif total_costs > 0:
            cost_impact_pct = 100.0
        else:
            cost_impact_pct = 0.0

        ls = report.long_vs_short
        nm = report.new_metrics
        ca = report.component_audit
        conc = report.concentration
        pr = report.parameter_robustness
        mc = report.monte_carlo
        wf = report.walk_forward

        res_item = {
            "combo_key": combo_key,
            "symbol": symbol,
            "category": category,
            "timeframe": tf_str,
            "status": "SUCCESS",
            "history_days": round(history_days, 1),
            "history_years": round(history_years, 2),
            "candle_count": candle_count,
            "effective_candles": effective,
            "first_candle": t_first[:10],
            "last_candle": t_last[:10],
            "trades": trades_n,
            "trades_per_month": freq["trades_per_month"],
            "trades_per_week": freq["trades_per_week"],
            "win_rate": round(m.win_rate, 4) if m else 0.0,
            "profit_factor": round(m.profit_factor, 4) if m else 0.0,
            "expectancy_R": round(nm.get("average_R", 0.0), 4),
            "median_R": round(nm.get("median_R", 0.0), 4),
            "gross_pnl": round(gross_pnl, 2),
            "total_costs": round(total_costs, 2),
            "net_pnl": round(net_pnl, 2),
            "gross_R": round(gross_R, 4),
            "net_R": round(net_R, 4),
            "max_drawdown": round(m.max_drawdown, 2) if m else 0.0,
            "max_drawdown_pct": round(m.max_drawdown_pct, 2) if m else 0.0,
            "cost_impact_pct": round(cost_impact_pct, 2),
            "top3_concentration_pct": round(conc.top_3_contribution_pct, 2),
            "parameter_stability_pct": round(pr.positive_combinations_pct, 2),
            "walk_forward_status": "STABLE" if wf.stability_pass else "UNSTABLE",
            "monte_carlo_probability_loss": round(mc.prob_final_loss_pct, 2),
            "long_PF": round(ls.get("LONG", {}).get("profit_factor", 0.0), 4),
            "short_PF": round(ls.get("SHORT", {}).get("profit_factor", 0.0), 4),
            "sample_size_status": ca.sample_size_classification if ca else "UNKNOWN",
            "robustness_classification": report.final_classification,
            "frequency_metrics": freq,
            "entry_dates": [s.entry_time for s in sims],
        }

        checkpoint_data[combo_key] = res_item
        save_checkpoint(checkpoint_data)

        elapsed = time.time() - t0
        log(f"[{idx:02d}/{n_total}] {symbol} {tf_str:<4} — concluído em {elapsed:.0f}s\n")

    mt5.shutdown()

    # ==============================================================
    # PROCESSAMENTO AGREGADO DE TODAS AS COMBINAÇÕES CONCLUÍDAS
    # ==============================================================
    log("\n=== CONSOLIDAÇÃO FINAL DE RESULTADOS (44 COMBINAÇÕES) ===")

    all_items = list(checkpoint_data.values())
    valid_items = [i for i in all_items if i.get("status") == "SUCCESS"]
    invalid_items = [i for i in all_items if i.get("status") != "SUCCESS"]

    log(f"Total de combinações testadas: {len(all_items)}")
    log(f"Combinações válidas: {len(valid_items)}")
    log(f"Combinações inválidas: {len(invalid_items)}")

    tot_candles = sum(i.get("candle_count", 0) for i in valid_items)
    tot_trades = sum(i.get("trades", 0) for i in valid_items)

    log(f"Total de candles processados: {tot_candles}")
    log(f"Total de trades acumulados: {tot_trades}\n")

    # MATRIZ COMPLETA
    log("=== MATRIZ COMPLETA ATIVO x TIMEFRAME ===")
    log(f"{'Symbol':<8} {'Cat':<8} {'TF':<4} {'Yrs':<5} {'Candles':<8} {'Trades':<7} {'T/Mês':<6} {'T/Sem':<6} {'WR%':<6} {'PF':<7} {'E(R)':<7} {'MedR':<7} {'DD%':<7} {'CostImp%':<9} {'Top3%':<7} {'ParStb%':<8} {'WF':<8} {'MC%':<6} {'LongPF':<7} {'ShrtPF':<7} {'SSize':<18} {'Class'}")
    for i in sorted(valid_items, key=lambda x: (x["symbol"], TIMEFRAMES.index(next(t for t in TIMEFRAMES if t["tf_str"] == x["timeframe"])))):
        log(f"{i['symbol']:<8} {i['category']:<8} {i['timeframe']:<4} {i['history_years']:<5.1f} {i['candle_count']:<8} {i['trades']:<7} {i['trades_per_month']:<6.1f} {i['trades_per_week']:<6.1f} {i['win_rate']*100:<6.1f} {i['profit_factor']:<7.3f} {i['expectancy_R']:<7.4f} {i['median_R']:<7.4f} {i['max_drawdown_pct']:<7.1f} {i['cost_impact_pct']:<9.1f} {i['top3_concentration_pct']:<7.1f} {i['parameter_stability_pct']:<8.1f} {i['walk_forward_status']:<8} {i['monte_carlo_probability_loss']:<6.1f} {i['long_PF']:<7.3f} {i['short_PF']:<7.3f} {i['sample_size_status']:<18} {i['robustness_classification']}")

    # ANÁLISE POR TIMEFRAME
    by_tf = defaultdict(list)
    for i in valid_items:
        by_tf[i["timeframe"]].append(i)

    tf_summary = {}
    log("\n=== COMPARAÇÃO AGREGADA POR TIMEFRAME ===")
    for tf_str in ["M15", "H1", "H4", "D1"]:
        items = by_tf[tf_str]
        if not items:
            continue
        pfs = [i["profit_factor"] for i in items if i["profit_factor"] > 0]
        exp_rs = [i["expectancy_R"] for i in items]
        dds = [i["max_drawdown_pct"] for i in items]
        costs = [i["cost_impact_pct"] for i in items]
        t_per_m = [i["trades_per_month"] for i in items]
        t_per_w = [i["trades_per_week"] for i in items]
        tot_tr = sum(i["trades"] for i in items)

        tf_summary[tf_str] = {
            "combos_count": len(items),
            "total_trades": tot_tr,
            "median_trades_per_month": round(float(np.median(t_per_m)), 2),
            "median_trades_per_week": round(float(np.median(t_per_w)), 2),
            "median_profit_factor": round(float(np.median(pfs)), 4) if pfs else 0.0,
            "median_expectancy_R": round(float(np.median(exp_rs)), 4),
            "median_drawdown_pct": round(float(np.median(dds)), 2),
            "median_cost_impact_pct": round(float(np.median(costs)), 2),
            "classifications_breakdown": dict(pd.Series([i["robustness_classification"] for i in items]).value_counts()),
        }

        log(f"\n--- TIMEFRAME {tf_str} ---")
        log(f"Total trades: {tot_tr} | Méd. T/Mês: {tf_summary[tf_str]['median_trades_per_month']} | Méd. T/Sem: {tf_summary[tf_str]['median_trades_per_week']}")
        log(f"Mediana PF: {tf_summary[tf_str]['median_profit_factor']} | Mediana E(R): {tf_summary[tf_str]['median_expectancy_R']}")
        log(f"Mediana DD%: {tf_summary[tf_str]['median_drawdown_pct']}% | Mediana Custo Impacto: {tf_summary[tf_str]['median_cost_impact_pct']}%")
        log(f"Classificações: {tf_summary[tf_str]['classifications_breakdown']}")

    # ANÁLISE POR MERCADO / CATEGORIA
    by_cat = defaultdict(list)
    for i in valid_items:
        by_cat[i["category"]].append(i)

    cat_summary = {}
    log("\n=== COMPARAÇÃO AGREGADA POR CATEGORIA DE MERCADO ===")
    for cat_str in ["FOREX", "METALS", "INDICES", "ENERGY", "CRYPTO"]:
        items = by_cat[cat_str]
        if not items:
            continue
        pfs = [i["profit_factor"] for i in items if i["profit_factor"] > 0]
        exp_rs = [i["expectancy_R"] for i in items]
        dds = [i["max_drawdown_pct"] for i in items]
        tot_tr = sum(i["trades"] for i in items)

        cat_summary[cat_str] = {
            "combos_count": len(items),
            "total_trades": tot_tr,
            "median_profit_factor": round(float(np.median(pfs)), 4) if pfs else 0.0,
            "median_expectancy_R": round(float(np.median(exp_rs)), 4),
            "median_drawdown_pct": round(float(np.median(dds)), 2),
            "classifications_breakdown": dict(pd.Series([i["robustness_classification"] for i in items]).value_counts()),
        }

        log(f"{cat_str:<8} — {len(items)} combos | Trades: {tot_tr:>4} | Med PF: {cat_summary[cat_str]['median_profit_factor']:<6.3f} | Med E(R): {cat_summary[cat_str]['median_expectancy_R']:<7.4f} | Med DD%: {cat_summary[cat_str]['median_drawdown_pct']:<6.1f}% | {cat_summary[cat_str]['classifications_breakdown']}")

    # FREQUÊNCIA GLOBAL DE PORTFÓLIO DE PRODUTO
    all_entry_records = []
    for i in valid_items:
        for d_str in i.get("entry_dates", []):
            all_entry_records.append({"combo_key": i["combo_key"], "symbol": i["symbol"], "timeframe": i["timeframe"], "timestamp": d_str, "date": d_str[:10]})

    portfolio_freq = {}
    if all_entry_records:
        pdf = pd.DataFrame(all_entry_records)
        all_timestamps = sorted(pdf["timestamp"].unique())
        t_min = pd.to_datetime(pdf["date"].min())
        t_max = pd.to_datetime(pdf["date"].max())
        total_span_years = max(0.1, (t_max - t_min).days / 365.25)
        total_opps = len(pdf)

        opps_yr = total_opps / total_span_years
        opps_mo = opps_yr / 12.0
        opps_wk = opps_yr / 52.0

        by_date = pdf.groupby("date")["combo_key"].count()
        dates_with_opp = len(by_date)
        max_same_day = int(by_date.max())
        pct_simultaneous = float((by_date[by_date > 1].sum() / total_opps * 100.0)) if total_opps > 0 else 0.0

        portfolio_freq = {
            "total_opportunities": total_opps,
            "total_span_years": round(total_span_years, 2),
            "opportunities_per_year": round(opps_yr, 1),
            "opportunities_per_month": round(opps_mo, 1),
            "opportunities_per_week": round(opps_wk, 1),
            "days_with_at_least_one_opportunity": dates_with_opp,
            "max_same_day_opportunities": max_same_day,
            "pct_simultaneous_events": round(pct_simultaneous, 1),
        }

        log("\n=== FREQUÊNCIA GLOBAL DE PORTFÓLIO DO PRODUTO ===")
        log(f"Total oportunidades: {total_opps} em {total_span_years:.2f} anos")
        log(f"Por ano: {opps_yr:.1f} | Por mês: {opps_mo:.1f} | Por semana: {opps_wk:.1f}")
        log(f"Dias com >= 1 oportunidade: {dates_with_opp}")
        log(f"Máximo de oportunidades no mesmo dia: {max_same_day}")
        log(f"% de eventos simultâneos: {pct_simultaneous:.1f}%")

    # CLASSIFICAÇÃO GERAL
    class_counts = dict(pd.Series([i["robustness_classification"] for i in valid_items]).value_counts())

    final_output = {
        "summary": {
            "total_planned": n_total,
            "valid_count": len(valid_items),
            "invalid_count": len(invalid_items),
            "total_candles": tot_candles,
            "total_trades": tot_trades,
            "classifications_breakdown": class_counts,
        },
        "timeframe_comparison": tf_summary,
        "market_comparison": cat_summary,
        "portfolio_frequency": portfolio_freq,
        "valid_combinations": valid_items,
        "invalid_combinations": invalid_items,
    }

    with open(FINAL_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, default=str)

    log(f"\nResultados salvos com sucesso em {FINAL_RESULTS_FILE}")

if __name__ == "__main__":
    run_experiment()
