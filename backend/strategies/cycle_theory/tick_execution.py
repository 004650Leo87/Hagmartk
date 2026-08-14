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
- Realized performance is reported in signed points and initial-risk R.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .broker import MockBroker, Position
from .enums import OrderType, PositionType


@dataclass(frozen=True)
class TickExecutionEvent:
    kind: str
    ticket: int
    price: float
    points: Optional[float] = None
    r_multiple: Optional[float] = None


class CycleTheoryTickExecutionHarness:
    def __init__(self, broker: MockBroker):
        self.broker = broker

        # Research-only bookkeeping.
        # Stores INITIAL risk by position ticket so later breakeven/trailing
        # modifications to position.sl cannot corrupt the R denominator.
        self._initial_risk_by_ticket: dict[int, Optional[float]] = {}

    def _register_initial_risk(self, position: Position) -> None:
        if position.ticket in self._initial_risk_by_ticket:
            return

        risk: Optional[float] = None

        if position.type is PositionType.BUY:
            if position.sl > 0 and position.price_open > position.sl:
                risk = position.price_open - position.sl

        else:
            if position.sl > 0 and position.sl > position.price_open:
                risk = position.sl - position.price_open

        self._initial_risk_by_ticket[position.ticket] = risk

    def _realized_metrics(
        self,
        position: Position,
        exit_price: float,
    ) -> tuple[float, Optional[float]]:
        if position.type is PositionType.BUY:
            price_delta = exit_price - position.price_open
        else:
            price_delta = position.price_open - exit_price

        points = round(
            price_delta / self.broker.point,
            8,
        )

        initial_risk = self._initial_risk_by_ticket.get(
            position.ticket
        )

        r_multiple: Optional[float] = None

        if initial_risk is not None and initial_risk > 0:
            r_multiple = round(
                price_delta / initial_risk,
                8,
            )

        return points, r_multiple

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

        # Capture initial risk of market positions before any exit processing.
        for position in list(self.broker.positions):
            self._register_initial_risk(position)

        # 1. Pending orders.
        for order in list(self.broker.pending_orders):
            should_fill = False

            if order.type is OrderType.BUY_LIMIT:
                should_fill = ask <= order.price_open

            elif order.type is OrderType.SELL_LIMIT:
                should_fill = bid >= order.price_open

            if not should_fill:
                continue

            position_ticket = self.broker.fill_pending(order.ticket)

            if position_ticket is None:
                continue

            position = next(
                (
                    p
                    for p in self.broker.positions
                    if p.ticket == position_ticket
                ),
                None,
            )

            if position is not None:
                self._register_initial_risk(position)

            events.append(
                TickExecutionEvent(
                    kind="LIMIT_FILLED",
                    ticket=position_ticket,
                    price=order.price_open,
                )
            )

        # 2. Open-position protective exits.
        for position in list(self.broker.positions):
            self._register_initial_risk(position)

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

            points, r_multiple = self._realized_metrics(
                position,
                exit_price,
            )

            if self.broker.position_close(position.ticket):
                events.append(
                    TickExecutionEvent(
                        kind=exit_kind,
                        ticket=position.ticket,
                        price=exit_price,
                        points=points,
                        r_multiple=r_multiple,
                    )
                )

        return events