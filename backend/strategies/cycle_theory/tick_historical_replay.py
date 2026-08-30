"""Tick-backed Cycle Theory V111 research replay.

Consumes observed Bid/Ask ticks in chronological order. This removes the OHLC
path assumption, but does not claim broker-faithful fill price or trading costs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

from .broker import Candle, PositionType
from .historical_replay import CycleTheoryHistoricalReplay, ReplayBar, ReplayResult, _atr


@dataclass(frozen=True)
class ReplayTick:
    time: datetime
    bid: float
    ask: float


class CycleTheoryTickHistoricalReplay(CycleTheoryHistoricalReplay):
    """Research replay using observed tick order and observed Bid/Ask spread."""

    def run_ticks(
        self,
        bars: Sequence[ReplayBar],
        ticks_by_bar: Mapping[datetime, Sequence[ReplayTick]],
        warmup_bars: int = 0,
    ) -> ReplayResult:
        ordered = sorted(bars, key=lambda item: item.time)
        if len(ordered) < 10:
            raise ValueError("Replay requires at least 10 candles.")

        self.adapter.power_on()
        eval_first = None
        eval_last = None
        eval_bars_count = 0
        terminal_bid = None
        terminal_ask = None

        for index, bar in enumerate(ordered):
            if index < warmup_bars:
                self._publish_history(ordered, index)
                continue

            ticks = sorted(ticks_by_bar.get(bar.time, ()), key=lambda item: item.time)
            if not ticks:
                continue
            if eval_first is None:
                eval_first = bar.time
            eval_last = bar.time
            eval_bars_count += 1
            observed_high = bar.open
            observed_low = bar.open

            for tick in ticks:
                observed_high = max(observed_high, tick.bid)
                observed_low = min(observed_low, tick.bid)
                partial = ReplayBar(
                    time=bar.time,
                    open=bar.open,
                    high=observed_high,
                    low=observed_low,
                    close=tick.bid,
                    spread_points=None,
                )
                visible = ordered[:index] + [partial]
                self._publish_history(visible, index)
                self.raw_broker.atr_value = _atr(visible, self.inputs.atr_period)
                self.execution.process_tick(bid=tick.bid, ask=tick.ask, at=tick.time)
                self.adapter.on_tick()
                terminal_bid = tick.bid
                terminal_ask = tick.ask

        summary = self.ledger.summary()
        terminal_unrealized_r = 0.0
        if terminal_bid is not None and terminal_ask is not None:
            for position in self.raw_broker.positions:
                record = self.ledger.get(position.ticket)
                if record is None or record.initial_risk is None or record.initial_risk <= 0:
                    continue
                if position.type is PositionType.BUY:
                    price_delta = terminal_bid - position.price_open
                else:
                    price_delta = position.price_open - terminal_ask
                raw_r = round(price_delta / record.initial_risk, 8)
                vol_frac = position.volume / record.initial_volume
                terminal_unrealized_r += round(raw_r * vol_frac, 8)

        terminal_unrealized_r = round(terminal_unrealized_r, 8)
        return ReplayResult(
            symbol=self.symbol,
            timeframe=self.timeframe,
            bars_processed=len(ordered),
            completed_trades=summary.trades,
            open_positions=len(self.raw_broker.positions),
            pending_orders=len(self.raw_broker.pending_orders),
            telemetry_events=len(self.adapter.sm.telemetry.events),
            summary=summary,
            execution_model="MT5_TICK_PATH_V1",
            cost_model=self.cost_model,
            fill_model="TICK_QUOTES_EXACT_LEVEL_FILL_MODEL",
            spread_model="OBSERVED_TICK_BID_ASK",
            terminal_unrealized_r=terminal_unrealized_r,
            mark_to_market_net_r=round(summary.net_r + terminal_unrealized_r, 8),
            evaluation_first_time=eval_first,
            evaluation_last_time=eval_last,
            evaluation_bars=eval_bars_count,
            warmup_bars=warmup_bars,
        )
