from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .core import ceil_grid, floor_grid
from .models import Candle, Direction, ExitDecision, InstrumentProfile, PriceSource, TradeLevels


@dataclass(frozen=True)
class ExecutableOHLC:
    bid_open: Decimal
    bid_high: Decimal
    bid_low: Decimal
    ask_open: Decimal
    ask_high: Decimal
    ask_low: Decimal


def executable_ohlc(candle: Candle, profile: InstrumentProfile) -> ExecutableOHLC:
    tick = profile.tick_size
    spread = Decimal(profile.spread_ticks) * tick
    if profile.source_price is PriceSource.BID:
        return ExecutableOHLC(
            bid_open=candle.open, bid_high=candle.high, bid_low=candle.low,
            ask_open=candle.open + spread, ask_high=candle.high + spread, ask_low=candle.low + spread,
        )
    half = spread / Decimal("2")
    return ExecutableOHLC(
        bid_open=floor_grid(candle.open - half, tick, profile.grid_origin),
        bid_high=floor_grid(candle.high - half, tick, profile.grid_origin),
        bid_low=floor_grid(candle.low - half, tick, profile.grid_origin),
        ask_open=ceil_grid(candle.open + half, tick, profile.grid_origin),
        ask_high=ceil_grid(candle.high + half, tick, profile.grid_origin),
        ask_low=ceil_grid(candle.low + half, tick, profile.grid_origin),
    )


def resolve_ohlc_exit(levels: TradeLevels, candle: Candle, t120: datetime,
                      profile: InstrumentProfile) -> ExitDecision | None:
    q = executable_ohlc(candle, profile)
    tick = profile.tick_size
    if levels.direction is Direction.LONG:
        open_stop = q.bid_open <= levels.stop
        open_target = q.bid_open >= levels.target
        if open_stop:
            price = q.bid_open - Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.open_time, detail="OPEN_GAP_STOP")
        if open_target:
            return ExitDecision("TARGET", levels.target, candle.open_time, detail="OPEN_REACHED_TARGET")
        if candle.open_time >= t120:
            price = q.bid_open - Decimal(profile.slippage_time_ticks) * tick
            return ExitDecision("TIME", price, candle.open_time)
        stop_hit = q.bid_low <= levels.stop
        target_hit = q.bid_high >= levels.target
        if stop_hit and target_hit:
            price = levels.stop - Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.close_time, detail="STOP_FIRST")
        if stop_hit:
            price = levels.stop - Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.close_time)
        if target_hit:
            return ExitDecision("TARGET", levels.target, candle.close_time)
    else:
        open_stop = q.ask_open >= levels.stop
        open_target = q.ask_open <= levels.target
        if open_stop:
            price = q.ask_open + Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.open_time, detail="OPEN_GAP_STOP")
        if open_target:
            return ExitDecision("TARGET", levels.target, candle.open_time, detail="OPEN_REACHED_TARGET")
        if candle.open_time >= t120:
            price = q.ask_open + Decimal(profile.slippage_time_ticks) * tick
            return ExitDecision("TIME", price, candle.open_time)
        stop_hit = q.ask_high >= levels.stop
        target_hit = q.ask_low <= levels.target
        if stop_hit and target_hit:
            price = levels.stop + Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.close_time, detail="STOP_FIRST")
        if stop_hit:
            price = levels.stop + Decimal(profile.slippage_stop_ticks) * tick
            return ExitDecision("STOP", price, candle.close_time)
        if target_hit:
            return ExitDecision("TARGET", levels.target, candle.close_time)
    return None
