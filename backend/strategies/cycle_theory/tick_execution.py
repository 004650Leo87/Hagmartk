"""Cycle Theory V111 — deterministic tick execution harness.

Research-only execution layer.

It does NOT change the V111 strategic rules. It drives the existing
MockBroker with deterministic Bid/Ask ticks to test execution lifecycle:
pending fills, SL and TP exits.

Execution conventions:
- BUY_LIMIT fills when Ask <= order price.
- SELL_LIMIT fills when Bid >= order price.
- BUY position SL/TP are evaluated against Bid.
- SELL position SL/TP are evaluated against Ask.
- Pending fills are processed before position exits on the same tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .broker import MockBroker
from .enums import OrderType, PositionType


@dataclass(frozen=True)
class TickExecutionEvent:
    kind: str
    ticket: int
    price: float


class CycleTheoryTickExecutionHarness:
    def __init__(self, broker: MockBroker):
        self.broker = broker

    def process_tick(
        self,
        bid: float,
        ask: float,
        at: Optional[datetime] = None,
    ) -> list[TickExecutionEvent]:

        if ask < bid:
            raise ValueError("ask must be >= bid")

        self.broker.bid = bid
        self.broker.ask = ask
        self.broker.spread_pts = round(
            (ask - bid) / self.broker.point
        )

        if at is not None:
            self.broker.now = at

        events: list[TickExecutionEvent] = []

        for order in list(self.broker.pending_orders):
            should_fill = False

            if order.type is OrderType.BUY_LIMIT:
                should_fill = ask <= order.price_open

            elif order.type is OrderType.SELL_LIMIT:
                should_fill = bid >= order.price_open

            if not should_fill:
                continue

            position_ticket = self.broker.fill_pending(order.ticket)

            if position_ticket is not None:
                events.append(
                    TickExecutionEvent(
                        kind="LIMIT_FILLED",
                        ticket=position_ticket,
                        price=order.price_open,
                    )
                )

        for position in list(self.broker.positions):
            exit_kind: Optional[str] = None
            exit_price: Optional[float] = None

            if position.type is PositionType.BUY:
                if position.sl > 0 and bid <= position.sl:
                    exit_kind = "STOP_LOSS"
                    exit_price = position.sl
                elif position.tp > 0 and bid >= position.tp:
                    exit_kind = "TAKE_PROFIT"
                    exit_price = position.tp

            else:
                if position.sl > 0 and ask >= position.sl:
                    exit_kind = "STOP_LOSS"
                    exit_price = position.sl
                elif position.tp > 0 and ask <= position.tp:
                    exit_kind = "TAKE_PROFIT"
                    exit_price = position.tp

            if exit_kind is None or exit_price is None:
                continue

            if self.broker.position_close(position.ticket):
                events.append(
                    TickExecutionEvent(
                        kind=exit_kind,
                        ticket=position.ticket,
                        price=exit_price,
                    )
                )

        return events