from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional
import numpy as np

from backend.backtest.simulator import TradeSimulation


@dataclass
class BacktestMetrics:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    payoff_ratio: float = 0.0
    expectancy: float = 0.0
    profit_factor: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_result: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    average_drawdown: float = 0.0
    recovery_factor: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    average_holding_time_bars: float = 0.0
    median_holding_time_bars: float = 0.0
    mae_average: float = 0.0
    mfe_average: float = 0.0
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    by_symbol: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_timeframe: Dict[str, Dict[str, float]] = field(default_factory=dict)
    by_direction: Dict[str, Dict[str, float]] = field(default_factory=dict)


def calculate_metrics(trades: List[TradeSimulation]) -> BacktestMetrics:
    """Calcula estatísticas rigorosas de performance para um conjunto de simulações de trades."""
    if not trades:
        return BacktestMetrics()

    total_trades = len(trades)
    wins_list = [t for t in trades if t.net_profit > 0]
    losses_list = [t for t in trades if t.net_profit < 0]
    breakevens_list = [t for t in trades if t.net_profit == 0]

    wins = len(wins_list)
    losses = len(losses_list)
    breakevens = len(breakevens_list)

    win_rate = (wins / total_trades) if total_trades > 0 else 0.0
    loss_rate = (losses / total_trades) if total_trades > 0 else 0.0

    gross_profit = sum(t.net_profit for t in wins_list)
    gross_loss = abs(sum(t.net_profit for t in losses_list))
    net_result = sum(t.net_profit for t in trades)

    average_win = (gross_profit / wins) if wins > 0 else 0.0
    average_loss = (gross_loss / losses) if losses > 0 else 0.0

    payoff_ratio = (average_win / average_loss) if average_loss > 0 else 0.0
    expectancy = (win_rate * average_win) - (loss_rate * average_loss)

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = gross_profit if gross_profit > 0 else 0.0

    # Sequências de Vitórias e Derrotas Consecutivas
    max_cons_wins = 0
    max_cons_losses = 0
    curr_wins = 0
    curr_losses = 0

    for t in trades:
        if t.net_profit > 0:
            curr_wins += 1
            curr_losses = 0
            if curr_wins > max_cons_wins:
                max_cons_wins = curr_wins
        elif t.net_profit < 0:
            curr_losses += 1
            curr_wins = 0
            if curr_losses > max_cons_losses:
                max_cons_losses = curr_losses
        else:
            curr_wins = 0
            curr_losses = 0

    # Retornos acumulados e Drawdown
    equity_curve = [0.0]
    cumulative = 0.0
    for t in trades:
        cumulative += t.net_profit
        equity_curve.append(cumulative)

    equity_arr = np.array(equity_curve)
    peak = np.maximum.accumulate(equity_arr)
    drawdowns = peak - equity_arr

    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
    avg_dd = float(np.mean(drawdowns[drawdowns > 0])) if np.any(drawdowns > 0) else 0.0

    peak_max = float(np.max(peak))
    max_dd_pct = (max_dd / peak_max * 100.0) if peak_max > 0 else 0.0

    recovery_factor = (net_result / max_dd) if max_dd > 0 else (net_result if net_result > 0 else 0.0)

    # Tempos de permanência (Holding time)
    holding_bars = [t.duration_bars for t in trades]
    avg_holding = float(np.mean(holding_bars)) if holding_bars else 0.0
    median_holding = float(np.median(holding_bars)) if holding_bars else 0.0

    # MAE e MFE médios
    maes = [t.mae for t in trades]
    mfes = [t.mfe for t in trades]
    avg_mae = float(np.mean(maes)) if maes else 0.0
    avg_mfe = float(np.mean(mfes)) if mfes else 0.0

    # Índices de Sharpe e Sortino
    pnls = np.array([t.net_profit for t in trades])
    std_pnl = float(np.std(pnls)) if len(pnls) > 1 else 0.0
    mean_pnl = float(np.mean(pnls)) if len(pnls) > 0 else 0.0

    sharpe = (mean_pnl / std_pnl * math.sqrt(252)) if std_pnl > 0 else None

    downside_pnls = pnls[pnls < 0]
    downside_std = float(np.std(downside_pnls)) if len(downside_pnls) > 1 else 0.0
    sortino = (mean_pnl / downside_std * math.sqrt(252)) if downside_std > 0 else None

    # Agregação por símbolo
    by_symbol: Dict[str, Dict[str, float]] = {}
    symbols_set = {t.event.symbol for t in trades}
    for sym in symbols_set:
        sym_trades = [t for t in trades if t.event.symbol == sym]
        sym_wins = sum(1 for t in sym_trades if t.net_profit > 0)
        sym_net = sum(t.net_profit for t in sym_trades)
        by_symbol[sym] = {
            "total_trades": len(sym_trades),
            "win_rate": sym_wins / len(sym_trades),
            "net_result": sym_net,
        }

    # Agregação por timeframe
    by_tf: Dict[str, Dict[str, float]] = {}
    tf_set = {t.event.timeframe for t in trades}
    for tf in tf_set:
        tf_trades = [t for t in trades if t.event.timeframe == tf]
        tf_wins = sum(1 for t in tf_trades if t.net_profit > 0)
        tf_net = sum(t.net_profit for t in tf_trades)
        by_tf[tf] = {
            "total_trades": len(tf_trades),
            "win_rate": tf_wins / len(tf_trades),
            "net_result": tf_net,
        }

    # Agregação por direção
    by_dir: Dict[str, Dict[str, float]] = {}
    dir_set = {t.event.direction.value for t in trades}
    for d in dir_set:
        d_trades = [t for t in trades if t.event.direction.value == d]
        d_wins = sum(1 for t in d_trades if t.net_profit > 0)
        d_net = sum(t.net_profit for t in d_trades)
        by_dir[d] = {
            "total_trades": len(d_trades),
            "win_rate": d_wins / len(d_trades),
            "net_result": d_net,
        }

    return BacktestMetrics(
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        breakevens=breakevens,
        win_rate=win_rate,
        loss_rate=loss_rate,
        average_win=average_win,
        average_loss=average_loss,
        payoff_ratio=payoff_ratio,
        expectancy=expectancy,
        profit_factor=profit_factor,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_result=net_result,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        average_drawdown=avg_dd,
        recovery_factor=recovery_factor,
        max_consecutive_wins=max_cons_wins,
        max_consecutive_losses=max_cons_losses,
        average_holding_time_bars=avg_holding,
        median_holding_time_bars=median_holding,
        mae_average=avg_mae,
        mfe_average=avg_mfe,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        by_symbol=by_symbol,
        by_timeframe=by_tf,
        by_direction=by_dir,
    )
