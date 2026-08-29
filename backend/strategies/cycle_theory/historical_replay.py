"""Cycle Theory V111 â€” historical OHLC replay.

Research-only. Does not modify the V111 strategic rules.

Intrabar execution model V0:
bullish candle: Open -> Low -> High -> Close
bearish candle: Open -> High -> Low -> Close

MT5 candle prices are treated as Bid. Ask is reconstructed from spread.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from .accounting_broker import AccountingBrokerBridge
from .broker import Candle, MockBroker
from .enums import PositionType
from .inputs import CycleTheoryInputs
from .realized_ledger import LedgerSummary, RealizedTradeLedger
from .research_adapter import CycleTheoryResearchAdapter
from .tick_execution import CycleTheoryTickExecutionHarness


@dataclass(frozen=True)
class ReplayBar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    spread_points: int | None = None


@dataclass(frozen=True)
class ReplayResult:
    symbol: str
    timeframe: str
    bars_processed: int
    completed_trades: int
    open_positions: int
    pending_orders: int
    telemetry_events: int
    summary: LedgerSummary
    execution_model: str = "OHLC_PATH_V0"
    terminal_unrealized_r: float = 0.0
    mark_to_market_net_r: float = 0.0
    evaluation_first_time: datetime | None = None
    evaluation_last_time: datetime | None = None
    evaluation_bars: int = 0
    warmup_bars: int = 0


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif hasattr(value, "to_pydatetime"):
        result = value.to_pydatetime()
    else:
        result = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    # V111 uses broker-server wall clock (TimeCurrent/iTime).
    # A timezone-aware timestamp cannot be relabelled as server time.
    if result.tzinfo is not None:
        raise ValueError(
            "Cycle Theory replay requires naive broker server time; "
            "timezone-aware input needs an explicit server time conversion."
        )

    return result


def replay_bars_from_records(
    records: Iterable[Mapping[str, Any]],
) -> list[ReplayBar]:

    result: list[ReplayBar] = []

    for row in records:
        spread = row.get("spread")

        result.append(
            ReplayBar(
                time=_datetime(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                spread_points=(
                    int(spread)
                    if spread is not None
                    else None
                ),
            )
        )

    result.sort(key=lambda item: item.time)

    return result


def replay_bars_from_dataframe(dataframe: Any) -> list[ReplayBar]:
    return replay_bars_from_records(
        dataframe.to_dict("records")
    )


def _path(bar: ReplayBar) -> tuple[float, ...]:
    if bar.close >= bar.open:
        return (
            bar.open,
            bar.low,
            bar.high,
            bar.close,
        )

    return (
        bar.open,
        bar.high,
        bar.low,
        bar.close,
    )


def _atr(
    bars: Sequence[ReplayBar],
    period: int,
) -> float:

    if period <= 0 or len(bars) < 2:
        return 0.0

    start = max(1, len(bars) - period)
    values: list[float] = []

    for index in range(start, len(bars)):
        current = bars[index]
        previous_close = bars[index - 1].close

        values.append(
            max(
                current.high - current.low,
                abs(current.high - previous_close),
                abs(current.low - previous_close),
            )
        )

    if not values:
        return 0.0

    return sum(values) / len(values)


class CycleTheoryHistoricalReplay:
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        inputs: CycleTheoryInputs,
        broker: MockBroker,
        default_spread_points: int = 10,
        max_history_bars: int = 5000,
    ) -> None:

        self.symbol = symbol
        self.timeframe = timeframe
        self.inputs = inputs
        self.raw_broker = broker
        self.default_spread_points = default_spread_points
        self.max_history_bars = max_history_bars

        self.ledger = RealizedTradeLedger(
            point=broker.point
        )

        self.broker = AccountingBrokerBridge(
            broker=broker,
            ledger=self.ledger,
        )

        self.adapter = CycleTheoryResearchAdapter(
            symbol=symbol,
            inputs=inputs,
            broker=self.broker,
            timeframe=timeframe,
            terms_accepted=True,
        )

        self.execution = CycleTheoryTickExecutionHarness(
            self.broker
        )

    def _publish_history(
        self,
        bars: Sequence[ReplayBar],
        index: int,
    ) -> None:

        start = max(
            0,
            index - self.max_history_bars + 1,
        )

        visible = bars[start:index + 1]

        series = [
            Candle(
                time=item.time,
                open=item.open,
                high=item.high,
                low=item.low,
                close=item.close,
            )
            for item in reversed(visible)
        ]

        self.raw_broker.set_bars(
            self.timeframe,
            series,
        )

    def run(
        self,
        bars: Sequence[ReplayBar],
        warmup_bars: int = 0,
    ) -> ReplayResult:

        ordered = sorted(
            bars,
            key=lambda item: item.time,
        )

        if len(ordered) < 10:
            raise ValueError(
                "Replay requires at least 10 candles."
            )

        self.adapter.power_on()

        eval_first: datetime | None = None
        eval_last: datetime | None = None
        eval_bars_count = 0

        for index, bar in enumerate(ordered):

            if index < warmup_bars:
                self._publish_history(ordered, index)
                continue

            if eval_first is None:
                eval_first = bar.time
            eval_last = bar.time
            eval_bars_count += 1

            spread_points = (
                bar.spread_points
                if bar.spread_points is not None
                else self.default_spread_points
            )

            spread = (
                spread_points
                * self.raw_broker.point
            )

            observed_high = bar.open
            observed_low = bar.open

            for bid in _path(bar):
                observed_high = max(observed_high, bid)
                observed_low = min(observed_low, bid)
                partial_bar = ReplayBar(
                    time=bar.time, open=bar.open, high=observed_high,
                    low=observed_low, close=bid, spread_points=bar.spread_points,
                )
                visible_bars = ordered[:index] + [partial_bar]
                self._publish_history(visible_bars, index)
                self.raw_broker.atr_value = _atr(
                    visible_bars, self.inputs.atr_period,
                )

                ask = bid + spread

                self.execution.process_tick(
                    bid=bid,
                    ask=ask,
                    at=bar.time,
                )

                self.adapter.on_tick()

        summary = self.ledger.summary()

        # Calculate terminal unrealized R
        terminal_unrealized_r = 0.0
        if ordered:
            terminal_candle = ordered[-1]
            terminal_spread = terminal_candle.spread_points if terminal_candle.spread_points is not None else self.default_spread_points
            terminal_bid = terminal_candle.close
            terminal_ask = terminal_bid + (terminal_spread * self.raw_broker.point)

            for position in self.raw_broker.positions:
                record = self.ledger.get(position.ticket)
                if record is not None and record.initial_risk is not None and record.initial_risk > 0:
                    if position.type is PositionType.BUY:
                        price_delta = terminal_bid - position.price_open
                    else:
                        price_delta = position.price_open - terminal_ask

                    raw_r = round(price_delta / record.initial_risk, 8)
                    vol_frac = position.volume / record.initial_volume
                    weighted_r = round(raw_r * vol_frac, 8)
                    terminal_unrealized_r += weighted_r

        terminal_unrealized_r = round(terminal_unrealized_r, 8)
        mark_to_market_net_r = round(summary.net_r + terminal_unrealized_r, 8)

        return ReplayResult(
            symbol=self.symbol,
            timeframe=self.timeframe,
            bars_processed=len(ordered),
            completed_trades=summary.trades,
            open_positions=len(
                self.raw_broker.positions
            ),
            pending_orders=len(
                self.raw_broker.pending_orders
            ),
            telemetry_events=len(
                self.adapter.sm.telemetry.events
            ),
            summary=summary,
            terminal_unrealized_r=terminal_unrealized_r,
            mark_to_market_net_r=mark_to_market_net_r,
            evaluation_first_time=eval_first,
            evaluation_last_time=eval_last,
            evaluation_bars=eval_bars_count,
            warmup_bars=warmup_bars,
        )
