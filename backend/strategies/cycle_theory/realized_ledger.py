"""Cycle Theory V111 — realized trade ledger.

Research-only accounting layer.

This module does NOT alter V111 strategic behavior or MockBroker fidelity.
It tracks normalized realized performance in initial-risk R, including
partial exits and final exits.

R is volume-weighted against the ORIGINAL position size and ORIGINAL risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .broker import Position
from .enums import PositionType


@dataclass(frozen=True)
class RealizedLeg:
    ticket: int
    volume: float
    exit_price: float
    points: float
    raw_r: Optional[float]
    weighted_r: Optional[float]
    kind: str


@dataclass
class TradeRecord:
    ticket: int
    symbol: str
    magic: int
    direction: PositionType

    entry_price: float
    initial_volume: float
    initial_sl: float
    initial_risk: Optional[float]

    remaining_volume: float

    legs: list[RealizedLeg] = field(default_factory=list)
    closed: bool = False

    @property
    def net_r(self) -> Optional[float]:
        values = [
            leg.weighted_r
            for leg in self.legs
            if leg.weighted_r is not None
        ]

        if not values:
            return None

        return round(sum(values), 8)

    @property
    def realized_volume(self) -> float:
        return round(
            sum(leg.volume for leg in self.legs),
            8,
        )


@dataclass(frozen=True)
class LedgerSummary:
    trades: int
    wins: int
    losses: int
    breakeven: int

    gross_positive_r: float
    gross_negative_r: float
    net_r: float

    expectancy_r: float
    profit_factor_r: Optional[float]


class RealizedTradeLedger:
    def __init__(self, point: float):
        if point <= 0:
            raise ValueError("point must be > 0")

        self.point = point
        self._records: dict[int, TradeRecord] = {}

    def register_position(
        self,
        position: Position,
    ) -> TradeRecord:

        existing = self._records.get(position.ticket)

        if existing is not None:
            return existing

        initial_risk: Optional[float] = None

        if position.type is PositionType.BUY:
            if (
                position.sl > 0
                and position.price_open > position.sl
            ):
                initial_risk = (
                    position.price_open - position.sl
                )

        else:
            if (
                position.sl > 0
                and position.sl > position.price_open
            ):
                initial_risk = (
                    position.sl - position.price_open
                )

        record = TradeRecord(
            ticket=position.ticket,
            symbol=position.symbol,
            magic=position.magic,
            direction=position.type,
            entry_price=position.price_open,
            initial_volume=position.volume,
            initial_sl=position.sl,
            initial_risk=initial_risk,
            remaining_volume=position.volume,
        )

        self._records[position.ticket] = record

        return record

    def get(
        self,
        ticket: int,
    ) -> Optional[TradeRecord]:
        return self._records.get(ticket)

    def _price_delta(
        self,
        record: TradeRecord,
        exit_price: float,
    ) -> float:

        if record.direction is PositionType.BUY:
            return exit_price - record.entry_price

        return record.entry_price - exit_price

    def record_exit(
        self,
        ticket: int,
        volume: float,
        exit_price: float,
        kind: str,
    ) -> RealizedLeg:

        record = self._records.get(ticket)

        if record is None:
            raise KeyError(
                f"position ticket {ticket} is not registered"
            )

        if record.closed:
            raise ValueError(
                f"position ticket {ticket} is already closed"
            )

        if volume <= 0:
            raise ValueError("exit volume must be > 0")

        if volume > record.remaining_volume + 1e-12:
            raise ValueError(
                "exit volume exceeds remaining position volume"
            )

        price_delta = self._price_delta(
            record,
            exit_price,
        )

        points = round(
            price_delta / self.point,
            8,
        )

        raw_r: Optional[float] = None
        weighted_r: Optional[float] = None

        if (
            record.initial_risk is not None
            and record.initial_risk > 0
        ):
            raw_r = round(
                price_delta / record.initial_risk,
                8,
            )

            volume_fraction = (
                volume / record.initial_volume
            )

            weighted_r = round(
                raw_r * volume_fraction,
                8,
            )

        leg = RealizedLeg(
            ticket=ticket,
            volume=volume,
            exit_price=exit_price,
            points=points,
            raw_r=raw_r,
            weighted_r=weighted_r,
            kind=kind,
        )

        record.legs.append(leg)

        record.remaining_volume = round(
            record.remaining_volume - volume,
            8,
        )

        if record.remaining_volume <= 1e-8:
            record.remaining_volume = 0.0
            record.closed = True

        return leg

    def record_partial(
        self,
        ticket: int,
        volume: float,
        exit_price: float,
    ) -> RealizedLeg:

        return self.record_exit(
            ticket=ticket,
            volume=volume,
            exit_price=exit_price,
            kind="PARTIAL",
        )

    def record_final(
        self,
        ticket: int,
        exit_price: float,
        kind: str,
    ) -> RealizedLeg:

        record = self._records.get(ticket)

        if record is None:
            raise KeyError(
                f"position ticket {ticket} is not registered"
            )

        return self.record_exit(
            ticket=ticket,
            volume=record.remaining_volume,
            exit_price=exit_price,
            kind=kind,
        )

    def completed_records(self) -> list[TradeRecord]:
        return [
            record
            for record in self._records.values()
            if record.closed
        ]

    def summary(self) -> LedgerSummary:
        completed = self.completed_records()

        normalized = [
            record
            for record in completed
            if record.net_r is not None
        ]

        values = [
            record.net_r
            for record in normalized
            if record.net_r is not None
        ]

        wins = sum(
            1
            for value in values
            if value > 1e-12
        )

        losses = sum(
            1
            for value in values
            if value < -1e-12
        )

        breakeven = sum(
            1
            for value in values
            if abs(value) <= 1e-12
        )

        gross_positive = round(
            sum(
                value
                for value in values
                if value > 0
            ),
            8,
        )

        gross_negative = round(
            sum(
                value
                for value in values
                if value < 0
            ),
            8,
        )

        net = round(
            sum(values),
            8,
        )

        expectancy = (
            round(net / len(values), 8)
            if values
            else 0.0
        )

        profit_factor: Optional[float]

        if gross_negative < 0:
            profit_factor = round(
                gross_positive / abs(gross_negative),
                8,
            )

        elif gross_positive > 0:
            profit_factor = None

        else:
            profit_factor = None

        return LedgerSummary(
            trades=len(values),
            wins=wins,
            losses=losses,
            breakeven=breakeven,
            gross_positive_r=gross_positive,
            gross_negative_r=gross_negative,
            net_r=net,
            expectancy_r=expectancy,
            profit_factor_r=profit_factor,
        )