"""Read-only MT5 execution-history evidence for Cycle Theory fidelity gates.

This module never sends, modifies, or cancels orders. It only joins historical
orders and deals to bound replay assumptions with broker-observed evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class ExecutionPair:
    symbol: str
    order_type: int
    order_reason: int
    order_price: float
    deal_reason: int
    deal_entry: int
    deal_price: float
    volume: float

    @property
    def delta(self) -> float:
        return round(self.deal_price - self.order_price, 10)

def collect_execution_pairs(mt5: Any, days: int = 180) -> list[ExecutionPair]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    orders = list(mt5.history_orders_get(start, end) or [])
    deals = list(mt5.history_deals_get(start, end) or [])
    deals_by_order: dict[int, list[Any]] = {}
    for deal in deals:
        deals_by_order.setdefault(int(deal.order), []).append(deal)

    pairs: list[ExecutionPair] = []
    for order in orders:
        for deal in deals_by_order.get(int(order.ticket), ()): 
            pairs.append(ExecutionPair(
                symbol=str(order.symbol),
                order_type=int(order.type),
                order_reason=int(order.reason),
                order_price=float(order.price_open),
                deal_reason=int(deal.reason),
                deal_entry=int(deal.entry),
                deal_price=float(deal.price),
                volume=float(deal.volume),
            ))
    return pairs


def summarize_execution_evidence(mt5: Any, pairs: list[ExecutionPair]) -> dict[str, Any]:
    limit_types = {int(mt5.ORDER_TYPE_BUY_LIMIT), int(mt5.ORDER_TYPE_SELL_LIMIT)}
    sl_tp_order_reasons = {int(mt5.ORDER_REASON_SL), int(mt5.ORDER_REASON_TP)}
    sl_tp_deal_reasons = {int(mt5.DEAL_REASON_SL), int(mt5.DEAL_REASON_TP)}

    pending = [p for p in pairs if p.order_type in limit_types and p.deal_entry == 0]
    protective = [p for p in pairs if p.order_reason in sl_tp_order_reasons or p.deal_reason in sl_tp_deal_reasons]

    def stats(rows: list[ExecutionPair]) -> dict[str, Any]:
        deltas = [p.delta for p in rows]
        return {
            "count": len(rows),
            "nonzero_delta_count": sum(1 for d in deltas if d != 0),
            "min_delta": min(deltas) if deltas else None,
            "max_delta": max(deltas) if deltas else None,
            "symbols": sorted({p.symbol for p in rows}),
        }

    return {"pending_limit": stats(pending), "sl_tp": stats(protective)}
