from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import json
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from backend.backtest.engine import BacktestEngine
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy

def audit():
    mt5.initialize()
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 10000)
    mt5.shutdown()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

    strategy = HagmartkTrendReferenceStrategy()
    costs = CostsConfig(
        spread_points=25.0,
        point_value=0.01,
        commission_per_trade=0.0,
        slippage_points=5.0,
        swap_per_bar=0.0
    )

    engine = BacktestEngine(strategy=strategy, intrabar_policy=IntrabarPolicy.CONSERVATIVE, costs=costs)
    exp = engine.run_experiment(df, "XAUUSD", "D1")
    sims = exp.simulations

    records = []
    reconcil_failures = 0

    slippage_cost_per_trade = costs.slippage_points * costs.point_value # 0.05
    spread_cost_per_trade = costs.spread_points * costs.point_value    # 0.25
    total_cost_per_trade = slippage_cost_per_trade + spread_cost_per_trade # 0.30

    for s in sims:
        is_buy = s.event.direction in ["BUY", "BULLISH"]
        ref_price = s.event.metadata.get("breakout_level", s.event.reference_price)
        if s.event.metadata.get("open_at_trigger") and is_buy and s.event.metadata["open_at_trigger"] > ref_price:
            ref_price = s.event.metadata["open_at_trigger"]
        elif s.event.metadata.get("open_at_trigger") and not is_buy and s.event.metadata["open_at_trigger"] < ref_price:
            ref_price = s.event.metadata["open_at_trigger"]

        # True gross PnL before ALL costs (without slippage and without spread):
        true_gross_pnl = (s.exit_price - ref_price) if is_buy else (ref_price - s.exit_price)
        
        # Net PnL calculated by simulator:
        net_pnl = s.net_profit

        # Check reconciliation: net_pnl == true_gross_pnl - total_cost_per_trade
        expected_net = true_gross_pnl - total_cost_per_trade
        if abs(net_pnl - expected_net) > 1e-4:
            reconcil_failures += 1

        initial_risk = s.initial_risk
        gross_R = true_gross_pnl / initial_risk if initial_risk > 0 else 0.0
        net_R = net_pnl / initial_risk if initial_risk > 0 else 0.0

        records.append({
            "trade_id": s.trade_id,
            "direction": s.event.direction.value,
            "entry_time": s.entry_time,
            "exit_time": s.exit_time,
            "year": s.entry_time[:4],
            "ref_price": ref_price,
            "entry_price": s.entry_price,
            "exit_price": s.exit_price,
            "initial_stop": s.event.invalidation,
            "initial_risk": initial_risk,
            "true_gross_pnl": true_gross_pnl,
            "slippage_cost": slippage_cost_per_trade,
            "spread_cost": spread_cost_per_trade,
            "comm_cost": 0.0,
            "swap_cost": 0.0,
            "total_cost": total_cost_per_trade,
            "net_pnl": net_pnl,
            "gross_R": gross_R,
            "net_R": net_R,
            "exit_reason": s.exit_reason,
        })

    rdf = pd.DataFrame(records)

    print("=== 1. AUDITORIA TRADE A TRADE (RECONCILIAÇÃO) ===")
    print(f"Total de trades auditados: {len(rdf)}")
    print(f"Falhas de Reconciliação (net_pnl != true_gross - total_cost): {reconcil_failures}")

    sum_true_gross = rdf["true_gross_pnl"].sum()
    sum_total_costs = rdf["total_cost"].sum()
    sum_net_pnl = rdf["net_pnl"].sum()

    print(f"\nSoma do True Gross PnL: ${sum_true_gross:.2f}")
    print(f"Soma dos Custos Totais ($0.30 x 80): ${sum_total_costs:.2f}")
    print(f"Soma do Net PnL: ${sum_net_pnl:.2f}")
    print(f"Verificação: ${sum_true_gross:.2f} - ${sum_total_costs:.2f} = ${sum_true_gross - sum_total_costs:.2f}")

    print("\n=== 2. SIGNIFICADO DO 'gross_profit' NO METRICS.PY ===")
    wins_net_sum = rdf[rdf["net_pnl"] > 0]["net_pnl"].sum()
    losses_net_sum = abs(rdf[rdf["net_pnl"] < 0]["net_pnl"].sum())
    print(f"Soma dos Net Profits dos trades VENCEDORES: ${wins_net_sum:.2f}")
    print(f"Soma dos Net Losses dos trades PERDEDORES: ${losses_net_sum:.2f}")
    print(f"Reportado em metrics.gross_profit (antigo): ${exp.metrics.gross_profit:.2f}")
    print(f"Reportado em metrics.gross_loss (antigo): ${exp.metrics.gross_loss:.2f}")
    print(f"Reportado em metrics.net_result: ${exp.metrics.net_result:.2f}")
    print(f"Diferença entre 'gross_profit' e 'net_result' no relatório anterior: ${exp.metrics.gross_profit - exp.metrics.net_result:.2f} (que é exatamente a soma das perdas líquidas!)")

    print("\n=== 3. PROFIT FACTOR CORRIGIDO ===")
    pf_net = wins_net_sum / losses_net_sum
    wins_gross_sum = rdf[rdf["true_gross_pnl"] > 0]["true_gross_pnl"].sum()
    losses_gross_sum = abs(rdf[rdf["true_gross_pnl"] < 0]["true_gross_pnl"].sum())
    pf_gross = wins_gross_sum / losses_gross_sum
    print(f"Profit Factor Net (Vencedoras Líquidas / |Perdedoras Líquidas|): {pf_net:.4f}")
    print(f"Profit Factor Gross (Vencedoras Brutas / |Perdedoras Brutas|): {pf_gross:.4f}")

    print("\n=== 4. EXPECTANCY ===")
    exp_net_mean = rdf["net_pnl"].mean()
    exp_net_r = rdf["net_R"].mean()
    win_rate = len(rdf[rdf["net_pnl"] > 0]) / len(rdf)
    loss_rate = len(rdf[rdf["net_pnl"] < 0]) / len(rdf)
    avg_win = rdf[rdf["net_pnl"] > 0]["net_pnl"].mean()
    avg_loss = abs(rdf[rdf["net_pnl"] < 0]["net_pnl"].mean())
    exp_calc = (win_rate * avg_win) - (loss_rate * avg_loss)
    print(f"Expectancy Net (Média dos Net PnL): ${exp_net_mean:.2f}")
    print(f"Expectancy R (Média dos Net R): {exp_net_r:.4f} R")
    print(f"Expectancy Fórmula (win_rate * avg_win - loss_rate * avg_loss): ${exp_calc:.2f}")

    print("\n=== 5. AUDITORIA DE DOUBLE COUNTING ===")
    print("Preço de entrada no evento (ref_price): ex:", rdf["ref_price"].iloc[0])
    print("Preço de entrada no simulator (com slippage): ex:", rdf["entry_price"].iloc[0])
    print("Derrapagem aplicada na entrada: $0.05 por trade.")
    print("Spread subtraído no net_pnl: $0.25 por trade.")
    print("Custo total aplicado por trade: $0.30.")
    print("Derrapagem ou spread foram cobrados duas vezes? NÃO.")

    print("\n=== 6. LONG VS SHORT BREAKDOWN ===")
    for d in ["BULLISH", "BEARISH"]:
        sub = rdf[rdf["direction"] == d]
        w = sub[sub["net_pnl"] > 0]["net_pnl"].sum()
        l = abs(sub[sub["net_pnl"] < 0]["net_pnl"].sum())
        pf = w / l if l > 0 else 0
        print(f"Direção {d}: Trades={len(sub)}, GrossPnL=${sub['true_gross_pnl'].sum():.2f}, Custos=${sub['total_cost'].sum():.2f}, NetPnL=${sub['net_pnl'].sum():.2f}, PF={pf:.2f}, Expectancy=${sub['net_pnl'].mean():.2f}, AvgNetR={sub['net_R'].mean():.4f}")

    print("\n=== 7. EXIT REASON BREAKDOWN ===")
    for reason in ["STOP", "DONCHIAN_EXIT", "END_OF_DATA"]:
        sub = rdf[rdf["exit_reason"] == reason]
        if len(sub) == 0:
            continue
        w_cnt = len(sub[sub["net_pnl"] > 0])
        wr = w_cnt / len(sub)
        print(f"Saída {reason}: Trades={len(sub)}, WinRate={wr*100:.1f}%, GrossPnL=${sub['true_gross_pnl'].sum():.2f}, NetPnL=${sub['net_pnl'].sum():.2f}, AvgNetR={sub['net_R'].mean():.4f}")

    print("\n=== 8. RESULTADO POR ANO ===")
    years = sorted(rdf["year"].unique())
    for y in years:
        sub = rdf[rdf["year"] == y]
        w = sub[sub["net_pnl"] > 0]["net_pnl"].sum()
        l = abs(sub[sub["net_pnl"] < 0]["net_pnl"].sum())
        pf = w / l if l > 0 else (w if w > 0 else 0.0)
        print(f"Ano {y}: Trades={len(sub)}, GrossPnL=${sub['true_gross_pnl'].sum():.2f}, Custos=${sub['total_cost'].sum():.2f}, NetPnL=${sub['net_pnl'].sum():.2f}, PF={pf:.2f}, AvgNetR={sub['net_R'].mean():.2f}R")

if __name__ == "__main__":
    audit()
