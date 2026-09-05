from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5

from backend.core.constants import TIMEFRAME_MINUTES
from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.run_cycle_theory_screening import _broker_for
from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.tick_historical_replay import (
    CycleTheoryTickHistoricalReplay,
    ReplayTick,
)
from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_data import (
    closed_normalized_candles,
    server_replay_bars,
)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected timezone-aware normalized MT5 timestamp")
    return parsed.astimezone(timezone.utc)


def _tick_groups(
    adapter: MT5MarketAdapter,
    clock: CycleTheoryBrokerClock,
    symbol: str,
    timeframe: str,
    normalized_candles: list[dict],
    warmup: int,
) -> tuple[dict[datetime, list[ReplayTick]], int, int]:
    minutes = TIMEFRAME_MINUTES[timeframe]
    eval_rows = normalized_candles[warmup:]
    starts_utc = [_utc(row["time"]) for row in eval_rows]
    if not starts_utc:
        return {}, 0, 0
    range_start = starts_utc[0]
    range_end = starts_utc[-1] + timedelta(minutes=minutes) - timedelta(milliseconds=1)

    raw_ticks = adapter.get_ticks(symbol, range_start, range_end)
    groups: dict[datetime, list[ReplayTick]] = {
        clock.utc_to_server_naive(start): [] for start in starts_utc
    }
    accepted = 0
    for row in raw_ticks:
        tick_utc = _utc(row["time"])
        index = bisect_right(starts_utc, tick_utc) - 1
        if index < 0:
            continue
        bar_start = starts_utc[index]
        if tick_utc >= bar_start + timedelta(minutes=minutes):
            continue
        bid = float(row["bid"])
        ask = float(row["ask"])
        if bid <= 0 or ask <= 0 or ask < bid:
            continue
        key = clock.utc_to_server_naive(bar_start)
        groups[key].append(
            ReplayTick(
                time=clock.utc_to_server_naive(tick_utc),
                bid=bid,
                ask=ask,
            )
        )
        accepted += 1

    groups = {key: value for key, value in groups.items() if value}
    return groups, len(raw_ticks), accepted


def _summary(result) -> dict:
    raw = asdict(result.summary)
    return {
        "trades": raw["trades"],
        "wins": raw["wins"],
        "losses": raw["losses"],
        "breakeven": raw["breakeven"],
        "net_r": raw["net_r"],
        "expectancy_r": raw["expectancy_r"],
        "profit_factor_r": raw["profit_factor_r"],
        "evaluation_bars": result.evaluation_bars,
        "execution_model": result.execution_model,
        "fill_model": result.fill_model,
        "spread_model": result.spread_model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cycle Theory V111 observed-tick replay comparison"
    )
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--timeframe", default="M30", choices=sorted(TIMEFRAME_MINUTES))
    parser.add_argument("--bars", type=int, default=300)
    parser.add_argument("--offset-bars", type=int, default=0)
    args = parser.parse_args()
    if args.bars <= 0:
        raise ValueError("--bars must be greater than zero")
    if args.offset_bars < 0:
        raise ValueError("--offset-bars cannot be negative")

    inputs = baseline_inputs()
    warmup = max(5, inputs.atr_period)
    adapter = MT5MarketAdapter()
    adapter.connect()

    try:
        scope = adapter.get_runtime_scope()
        clock = CycleTheoryBrokerClock.from_runtime_scope(scope)
        candles = adapter.get_candles(
            args.symbol,
            args.timeframe,
            count=args.bars + warmup + args.offset_bars + 2,
        )
        candles = closed_normalized_candles(candles, args.timeframe)
        if args.offset_bars:
            candles = candles[:-args.offset_bars]
        candles = candles[-(args.bars + warmup):]
        if len(candles) < args.bars + warmup:
            raise RuntimeError("Insufficient closed candles for tick replay window")
        bars = server_replay_bars(candles, clock)

        tick_groups, raw_tick_count, accepted_tick_count = _tick_groups(
            adapter, clock, args.symbol, args.timeframe, candles, warmup
        )

        ohlc = CycleTheoryHistoricalReplay(
            args.symbol,
            args.timeframe,
            inputs,
            _broker_for(args.symbol),
            default_spread_points=int(getattr(mt5.symbol_info(args.symbol), "spread", 10) or 10),
        ).run(bars, warmup_bars=warmup)

        tick_replay = CycleTheoryTickHistoricalReplay(
            args.symbol,
            args.timeframe,
            inputs,
            _broker_for(args.symbol),
            default_spread_points=int(getattr(mt5.symbol_info(args.symbol), "spread", 10) or 10),
        ).run_ticks(bars, tick_groups, warmup_bars=warmup)

        ohlc_summary = _summary(ohlc)
        tick_summary = _summary(tick_replay)
        expected_eval_bars = len(bars) - warmup
        covered_bars = len(tick_groups)

        print("=" * 76)
        print("CYCLE THEORY V111 - OBSERVED TICK REPLAY COMPARISON")
        print("=" * 76)
        print(
            f"{args.symbol} {args.timeframe} | offset={args.offset_bars} | closed bars={expected_eval_bars} "
            f"| tick-covered bars={covered_bars}"
        )
        print(f"raw ticks={raw_tick_count} | accepted Bid/Ask ticks={accepted_tick_count}")
        print("-" * 76)
        print("OHLC MODEL")
        print(ohlc_summary)
        print("OBSERVED TICKS")
        print(tick_summary)
        print("-" * 76)
        print(
            "delta trades="
            f"{tick_summary['trades'] - ohlc_summary['trades']}"
            " | delta netR="
            f"{tick_summary['net_r'] - ohlc_summary['net_r']:.4f}"
            " | delta expectancy="
            f"{tick_summary['expectancy_r'] - ohlc_summary['expectancy_r']:.4f}R"
        )
        print(
            "BOUNDARY: observed tick order/spread only. Broker acceptance, slippage, "
            "commission and swap remain partial/modelled. No real orders sent."
        )
        print("=" * 76)
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
