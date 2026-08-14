"""Cycle Theory V111 — accounting broker bridge.

Research-only wrapper around MockBroker.

It preserves broker behavior while mirroring realized execution into
RealizedTradeLedger. Strategic logic remains untouched.
"""

from __future__ import annotations

from typing import Optional

from .broker import MockBroker, Position
from .enums import PositionType
from .realized_ledger import RealizedTradeLedger


class AccountingBrokerBridge:
    def __init__(
        self,
        broker: MockBroker,
        ledger: RealizedTradeLedger,
    ):
        self._broker = broker
        self.ledger = ledger

    def __getattr__(self, name):
        return getattr(self._broker, name)

    @property
    def bid(self) -> float:
        return self._broker.bid

    @bid.setter
    def bid(self, value: float) -> None:
        self._broker.bid = value

    @property
    def ask(self) -> float:
        return self._broker.ask

    @ask.setter
    def ask(self, value: float) -> None:
        self._broker.ask = value

    @property
    def spread_pts(self) -> int:
        return self._broker.spread_pts

    @spread_pts.setter
    def spread_pts(self, value: int) -> None:
        self._broker.spread_pts = value

    def _position_by_ticket(
        self,
        ticket: int,
    ) -> Optional[Position]:
        for position in self._broker.positions:
            if position.ticket == ticket:
                return position
        return None

    def _register_ticket(
        self,
        ticket: Optional[int],
    ) -> Optional[int]:
        if ticket is None:
            return None

        position = self._position_by_ticket(ticket)

        if position is not None:
            self.ledger.register_position(position)

        return ticket

    def buy(
        self,
        volume: float,
        sl: float,
        tp: float,
        magic: int,
    ) -> Optional[int]:
        return self._register_ticket(
            self._broker.buy(
                volume,
                sl,
                tp,
                magic,
            )
        )

    def sell(
        self,
        volume: float,
        sl: float,
        tp: float,
        magic: int,
    ) -> Optional[int]:
        return self._register_ticket(
            self._broker.sell(
                volume,
                sl,
                tp,
                magic,
            )
        )

    def buy_limit(
        self,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        magic: int,
    ) -> Optional[int]:
        return self._broker.buy_limit(
            volume,
            price,
            sl,
            tp,
            magic,
        )

    def sell_limit(
        self,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        magic: int,
    ) -> Optional[int]:
        return self._broker.sell_limit(
            volume,
            price,
            sl,
            tp,
            magic,
        )

    def fill_pending(
        self,
        ticket: int,
    ) -> Optional[int]:
        position_ticket = self._broker.fill_pending(ticket)

        return self._register_ticket(position_ticket)

    def position_modify(
        self,
        ticket: int,
        sl: float,
        tp: float,
    ) -> bool:
        return self._broker.position_modify(
            ticket,
            sl,
            tp,
        )

    def position_close_partial(
        self,
        ticket: int,
        volume: float,
        profit: float = 0.0,
    ) -> bool:

        position = self._position_by_ticket(ticket)

        if position is None:
            return False

        self.ledger.register_position(position)

        if position.type is PositionType.BUY:
            exit_price = self._broker.bid
        else:
            exit_price = self._broker.ask

        remaining_before = position.volume

        ok = self._broker.position_close_partial(
            ticket,
            volume,
            profit,
        )

        if not ok:
            return False

        realized_volume = min(
            volume,
            remaining_before,
        )

        if realized_volume >= remaining_before:
            self.ledger.record_final(
                ticket=ticket,
                exit_price=exit_price,
                kind="PARTIAL_100",
            )
        else:
            self.ledger.record_partial(
                ticket=ticket,
                volume=realized_volume,
                exit_price=exit_price,
            )

        return True

    def position_close_at(
        self,
        ticket: int,
        exit_price: float,
        kind: str = "FINAL_CLOSE",
        profit: float = 0.0,
    ) -> bool:
        """Fecha no broker e contabiliza no preço de execução explícito."""

        position = self._position_by_ticket(ticket)

        if position is None:
            return False

        self.ledger.register_position(position)

        ok = self._broker.position_close(
            ticket,
            profit,
        )

        if not ok:
            return False

        self.ledger.record_final(
            ticket=ticket,
            exit_price=exit_price,
            kind=kind,
        )

        return True

    def position_close(
        self,
        ticket: int,
        profit: float = 0.0,
    ) -> bool:

        position = self._position_by_ticket(ticket)

        if position is None:
            return False

        if position.type is PositionType.BUY:
            exit_price = self._broker.bid
        else:
            exit_price = self._broker.ask

        return self.position_close_at(
            ticket=ticket,
            exit_price=exit_price,
            kind="FINAL_CLOSE",
            profit=profit,
        )

    def close_all_by_magic(
        self,
        magic: int,
    ) -> None:
        """Preserva CloseAllOperations por magic e contabiliza saídas."""
        tickets = [
            position.ticket
            for position in list(self._broker.positions)
            if position.magic == magic
        ]

        for ticket in tickets:
            self.position_close(ticket)

        for order in list(self._broker.pending_orders):
            if order.magic == magic:
                self._broker.order_delete(order.ticket)
