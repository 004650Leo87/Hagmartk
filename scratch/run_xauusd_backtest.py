from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import json
from datetime import datetime, timezone
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from backend.backtest.engine import BacktestEngine
from backend.backtest.simulator import CostsConfig, IntrabarPolicy
from backend.domain.events import Direction
from backend.strategies.trend_reference import HagmartkTrendReferenceStrategy


def run_backtest():
    print("=== CONECTANDO AO MT5 PARA OBTER HISTÓRICO DE XAUUSD D1 ===")
    if not mt5.initialize():
        print(f"Erro ao inicializar MT5: {mt5.last_error()}")
        return

    symbol = "XAUUSD"
    timeframe_str = "D1"
    tf = mt5.TIMEFRAME_D1

    # Busca o maior número possível de candles D1 disponíveis (ex: 10.000 barras)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, 10000)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print(f"Não foi possível obter dados históricos para {symbol} {timeframe_str}")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")

    candle_count_total = len(df)
    start_date = df["time"].iloc[0]
    end_date = df["time"].iloc[-1]

    print(f"Histórico retornado do MT5: {candle_count_total} candles D1 ({start_date} até {end_date})")

    strategy = HagmartkTrendReferenceStrategy()
    costs = CostsConfig(
        spread_points=25.0,        # 25 pontos (~$0.25 no ouro)
        point_value=0.01,
        commission_per_trade=0.0,
        slippage_points=5.0,       # 5 pontos (~$0.05 no ouro)
        swap_per_bar=0.0,
    )

    engine = BacktestEngine(
        strategy=strategy,
        intrabar_policy=IntrabarPolicy.CONSERVATIVE,
        costs=costs,
        in_sample_ratio=0.70,
    )

    exp = engine.run_experiment(df, symbol=symbol, timeframe=timeframe_str)
    print(f"Status do Experimento: {exp.status}")
    if exp.status != "SUCCESS":
        print(f"Motivo da falha: {exp.failure_reason}")
        return

    sims = exp.simulations
    metrics = exp.metrics
    warmup_bars = strategy.warmup_bars
    effective_candles = max(0, candle_count_total - warmup_bars)

    longs = [s for s in sims if s.event.direction in (Direction.BUY, Direction.BULLISH)]
    shorts = [s for s in sims if s.event.direction in (Direction.SELL, Direction.BEARISH)]

    stop_exits = [s for s in sims if s.exit_reason == "STOP"]
    donchian_exits = [s for s in sims if s.exit_reason == "DONCHIAN_EXIT"]
    end_of_data_exits = [s for s in sims if s.exit_reason == "END_OF_DATA"]
    ambiguous_rejected = strategy.ambiguous_events_count

    r_gross_list = [s.r_multiple_gross for s in sims]
    r_net_list = [s.r_multiple_net for s in sims]

    avg_r_gross = float(np.mean(r_gross_list)) if r_gross_list else 0.0
    avg_r_net = float(np.mean(r_net_list)) if r_net_list else 0.0

    r_dist = {}
    if r_net_list:
        r_dist = {
            "min": float(np.min(r_net_list)),
            "p25": float(np.percentile(r_net_list, 25)),
            "median": float(np.median(r_net_list)),
            "p75": float(np.percentile(r_net_list, 75)),
            "max": float(np.max(r_net_list)),
        }

    wins = [s for s in sims if s.net_profit > 0]
    losses = [s for s in sims if s.net_profit < 0]

    first_trade = sims[0] if sims else None
    last_trade = sims[-1] if sims else None

    win_samples = wins[:3] if len(wins) >= 3 else wins
    loss_samples = losses[:3] if len(losses) >= 3 else losses

    seen_ids = set()
    sample_list = []

    for t in [first_trade, last_trade] + win_samples + loss_samples:
        if t and t.trade_id not in seen_ids:
            seen_ids.add(t.trade_id)
            sample_list.append(t)

    audit_records = []
    for s in sample_list:
        audit_records.append({
            "trade_id": s.trade_id,
            "detected_at": s.event.detected_at,
            "direction": s.event.direction.value,
            "breakout_level": s.event.metadata.get("breakout_level"),
            "entry_price": s.entry_price,
            "n_at_entry": s.event.metadata.get("n_at_entry"),
            "initial_stop": s.event.metadata.get("initial_stop"),
            "exit_time": s.exit_time,
            "exit_price": s.exit_price,
            "exit_reason": s.exit_reason,
            "gross_profit": s.gross_profit,
            "net_profit": s.net_profit,
            "r_multiple_net": s.r_multiple_net,
            "duration_bars": s.duration_bars,
        })

    report = {
        "periodo_analisado": f"{start_date} ate {end_date}",
        "candle_count_total": candle_count_total,
        "candle_count_efetivo": effective_candles,
        "quantidade_operacoes": len(sims),
        "longs": len(longs),
        "shorts": len(shorts),
        "vencedoras": metrics.wins,
        "perdedoras": metrics.losses,
        "breakevens": metrics.breakevens,
        "win_rate": metrics.win_rate,
        "loss_rate": metrics.loss_rate,
        "lucro_medio": metrics.average_win,
        "prejuizo_medio": metrics.average_loss,
        "payoff": metrics.payoff_ratio,
        "expectancy": metrics.expectancy,
        "profit_factor": metrics.profit_factor,
        "resultado_bruto": metrics.gross_profit,
        "resultado_liquido": metrics.net_result,
        "max_drawdown": metrics.max_drawdown,
        "drawdown_pct": metrics.max_drawdown_pct,
        "recovery_factor": metrics.recovery_factor,
        "maior_seq_ganhos": metrics.max_consecutive_wins,
        "maior_seq_perdas": metrics.max_consecutive_losses,
        "duracao_media_bars": metrics.average_holding_time_bars,
        "duracao_mediana_bars": metrics.median_holding_time_bars,
        "mae_medio": metrics.mae_average,
        "mfe_medio": metrics.mfe_average,
        "sharpe": metrics.sharpe_ratio,
        "sortino": metrics.sortino_ratio,
        "avg_r_gross": avg_r_gross,
        "avg_r_net": avg_r_net,
        "distribuicao_r_net": r_dist,
        "qtd_stop": len(stop_exits),
        "qtd_donchian_exit": len(donchian_exits),
        "qtd_end_of_data": len(end_of_data_exits),
        "qtd_ambiguous_dual_breakout": ambiguous_rejected,
        "custos_totais_config": {
            "spread_points": costs.spread_points,
            "point_value": costs.point_value,
            "slippage_points": costs.slippage_points,
        },
        "in_sample": {
            "trades": exp.in_sample_metrics.total_trades,
            "net_result": exp.in_sample_metrics.net_result,
            "profit_factor": exp.in_sample_metrics.profit_factor,
            "win_rate": exp.in_sample_metrics.win_rate,
        },
        "out_of_sample": {
            "trades": exp.out_of_sample_metrics.total_trades,
            "net_result": exp.out_of_sample_metrics.net_result,
            "profit_factor": exp.out_of_sample_metrics.profit_factor,
            "win_rate": exp.out_of_sample_metrics.win_rate,
        },
        "amostra_auditavel": audit_records,
    }

    print("\n=== RESULTADO DO EXPERIMENTO XAUUSD D1 ===")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_backtest()
