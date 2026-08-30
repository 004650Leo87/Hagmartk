"""Read-only MT5 order-state evidence for Cycle Theory fidelity.

Historical orders only: this module never sends, modifies, or cancels orders.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any


def collect_order_state_evidence(mt5: Any, days: int = 180) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    orders = list(mt5.history_orders_get(start, end) or [])
    names = {
        value: name for name in dir(mt5) for value in [getattr(mt5, name)]
        if name.startswith("ORDER_STATE_") and isinstance(value, int)
    }
    counts = Counter(int(order.state) for order in orders)
    by_state = {names.get(state, str(state)): count for state, count in counts.items()}
    rejected = [o for o in orders if int(o.state) == int(mt5.ORDER_STATE_REJECTED)]
    canceled = [o for o in orders if int(o.state) == int(mt5.ORDER_STATE_CANCELED)]
    return {
        "total_orders": len(orders),
        "by_state": by_state,
        "rejected_count": len(rejected),
        "canceled_count": len(canceled),
        "rejected_symbols": sorted({str(o.symbol) for o in rejected}),
        "canceled_symbols": sorted({str(o.symbol) for o in canceled}),
    }

