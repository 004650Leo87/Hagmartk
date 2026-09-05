from __future__ import annotations

import argparse
from dataclasses import asdict

import MetaTrader5 as mt5

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import (
    CycleTheoryHistoricalReplay,
    ReplayBar,
)
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_data import (
    closed_normalized_candles,
    server_replay_bars,
)


TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
}


def _server_bars(candles: list[dict], clock: CycleTheoryBrokerClock) -> list[ReplayBar]:
    return server_replay_bars(candles, clock)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cycle Theory V111 research replay on the scoped MT5 runtime."
    )
    parser.add_argument("--symbol", default="EURUSD")
    parser.add_argument("--timeframe", default="M5", choices=TIMEFRAMES)
    parser.add_argument("--bars", type=int, default=5000)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument(
        "--warmup",
        type=int,
        default=None,
        help="Context bars before evaluation; default derives from ATR period.",
    )
    args = parser.parse_args()

    if args.bars <= 0:
        raise ValueError("--bars must be greater than zero")
    if args.offset < 0:
        raise ValueError("--offset cannot be negative")

    adapter = MT5MarketAdapter()
    adapter.connect()

    try:
        scope = adapter.get_runtime_scope()
        clock = CycleTheoryBrokerClock.from_runtime_scope(scope)
        inputs = baseline_inputs()
        warmup_bars = args.warmup
        if warmup_bars is None:
            warmup_bars = max(5, inputs.atr_period)
        if warmup_bars < 0:
            raise ValueError("--warmup cannot be negative")

        requested = args.bars + warmup_bars + args.offset + 2
        candles = adapter.get_candles(
            args.symbol,
            args.timeframe,
            count=requested,
        )
        candles = closed_normalized_candles(candles, args.timeframe)
        if args.offset:
            candles = candles[:-args.offset]
        candles = candles[-(args.bars + warmup_bars):]
        if len(candles) < args.bars + warmup_bars:
            raise RuntimeError("Insufficient closed candles for requested replay window")
        bars = _server_bars(candles, clock)

        info = mt5.symbol_info(args.symbol)
        if info is None:
            raise RuntimeError(f"Symbol not available: {args.symbol}")

        broker = MockBroker(
            symbol=args.symbol,
            point=float(info.point),
            digits=int(info.digits),
            stops_level_pts=int(getattr(info, "trade_stops_level", 0) or 0),
            freeze_level_pts=int(getattr(info, "trade_freeze_level", 0) or 0),
            volume_step=float(getattr(info, "volume_step", 0.01) or 0.01),
            volume_min=float(getattr(info, "volume_min", 0.01) or 0.01),
            volume_max=float(getattr(info, "volume_max", 100.0) or 100.0),
        )

        replay = CycleTheoryHistoricalReplay(
            symbol=args.symbol,
            timeframe=args.timeframe,
            inputs=inputs,
            broker=broker,
            default_spread_points=int(getattr(info, "spread", 10) or 10),
        )
        result = replay.run(bars, warmup_bars=warmup_bars)
        summary = asdict(result.summary)

        print()
        print("=" * 72)
        print("CYCLE THEORY V111 - HISTORICAL REPLAY (RESEARCH ONLY)")
        print("=" * 72)
        print(
            f"runtime={scope.get('server', 'UNKNOWN')}"
            f" | clock={clock.policy_id}"
            f" | offset={clock.offset_hours:+g}h"
        )
        print(
            f"{result.symbol} {result.timeframe}"
            f" | evaluation bars={result.evaluation_bars}"
            f" | warmup={result.warmup_bars}"
        )
        print(f"execution model={result.execution_model}")
        print(f"cost model={result.cost_model}")
        print(f"fill model={result.fill_model}")
        print(f"spread model={result.spread_model}")
        print("-" * 72)
        print(f"evaluation start={result.evaluation_first_time}")
        print(f"evaluation end  ={result.evaluation_last_time}")
        print("-" * 72)
        print(
            f"trades={summary['trades']} | wins={summary['wins']}"
            f" | losses={summary['losses']} | BE={summary['breakeven']}"
        )
        print(
            f"realized net R={summary['net_r']:.4f}"
            f" | expectancy={summary['expectancy_r']:.4f}R"
            f" | PF_R={summary['profit_factor_r']}"
        )
        print(
            f"terminal unrealized R={result.terminal_unrealized_r:.4f}"
            f" | mark-to-market net R={result.mark_to_market_net_r:.4f}"
        )
        print(
            f"open positions={result.open_positions}"
            f" | pending={result.pending_orders}"
            f" | telemetry={result.telemetry_events}"
        )
        print("-" * 72)
        print(
            "BOUNDARY: OHLC path, fill and costs remain modelled/partial; "
            "no real-order or profitability claim."
        )
        print("=" * 72)

    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
