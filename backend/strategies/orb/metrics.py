from __future__ import annotations

from decimal import Decimal
import math
from typing import Iterable

from .models import TradeRecord


def wilson_95(successes: int, total: int):
    if total <= 0:
        return None
    p = successes / total
    z = 1.959963984540054
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return (max(0.0, center - half), min(1.0, center + half))


def summarize_trades(records: Iterable[TradeRecord]) -> dict:
    trades = list(records)
    n = len(trades)
    if n == 0:
        return {
            "N": 0, "expectancy_R": None, "p_win": None, "p_loss": None,
            "p_zero": None, "p_target": None, "profit_factor": None,
            "pnl_net_sum": Decimal("0"), "pnl_net_mean": None,
            "max_negative_streak": 0, "wilson_win_95": None,
        }
    wins = [t for t in trades if t.pnl_net > 0]
    losses = [t for t in trades if t.pnl_net < 0]
    zeros = [t for t in trades if t.pnl_net == 0]
    targets = [t for t in trades if t.exit_reason == "TARGET"]
    sum_pos = sum((t.pnl_net for t in wins), Decimal("0"))
    sum_neg = sum((t.pnl_net for t in losses), Decimal("0"))
    if sum_neg < 0:
        pf = sum_pos / abs(sum_neg)
    elif sum_pos > 0:
        pf = Decimal("Infinity")
    else:
        pf = None
    streak = max_streak = 0
    for trade in trades:
        if trade.pnl_net < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    total_r = sum((t.r_multiple for t in trades), Decimal("0"))
    pnl_sum = sum((t.pnl_net for t in trades), Decimal("0"))
    return {
        "N": n,
        "expectancy_R": total_r / Decimal(n),
        "p_win": len(wins) / n,
        "p_loss": len(losses) / n,
        "p_zero": len(zeros) / n,
        "p_target": len(targets) / n,
        "profit_factor": pf,
        "pnl_net_sum": pnl_sum,
        "pnl_net_mean": pnl_sum / Decimal(n),
        "max_negative_streak": max_streak,
        "wilson_win_95": wilson_95(len(wins), n),
    }


def build_trade_record(direction, quantity, entry, exit_price, point_value, costs_cash, risk_cash, exit_reason):
    from .core import linear_profit
    pnl_gross = linear_profit(direction, quantity, entry, exit_price, point_value)
    pnl_net = pnl_gross - costs_cash
    if risk_cash <= 0:
        raise ValueError("R_cash must be positive")
    return TradeRecord(
        direction=direction,
        pnl_gross=pnl_gross,
        costs_cash=costs_cash,
        pnl_net=pnl_net,
        risk_cash=risk_cash,
        r_multiple=pnl_net / risk_cash,
        exit_reason=exit_reason,
    )
