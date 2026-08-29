from __future__ import annotations

import argparse
from dataclasses import asdict

import MetaTrader5 as mt5

from backend.services.market_service import MarketService
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import (
    CycleTheoryHistoricalReplay,
    replay_bars_from_dataframe,
)
from backend.strategies.cycle_theory.inputs import baseline_inputs


TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbol",
        default="EURUSD",
    )

    parser.add_argument(
        "--timeframe",
        default="M5",
        choices=TIMEFRAMES,
    )

    parser.add_argument(
        "--bars",
        type=int,
        default=5000,
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=0,
    )

    parser.add_argument(
        "--warmup",
        type=int,
        default=None,
        help="Warmup bars before evaluation. If None, derived dynamically."
    )

    args = parser.parse_args()

    service = MarketService()

    try:
        inputs = baseline_inputs()

        warmup_bars = args.warmup
        if warmup_bars is None:
            warmup_bars = max(5, inputs.atr_period)

        dataframe = service.candles(
            args.symbol,
            TIMEFRAMES[args.timeframe],
            bars=args.bars + warmup_bars,
            offset=args.offset,
        )

        info = mt5.symbol_info(
            args.symbol
        )

        if info is None:
            raise RuntimeError(
                f"Symbol not available: {args.symbol}"
            )

        broker = MockBroker(
            symbol=args.symbol,
            point=float(info.point),
            digits=int(info.digits),
            stops_level_pts=int(
                getattr(info, "trade_stops_level", 0)
                or 0
            ),
            freeze_level_pts=int(
                getattr(info, "trade_freeze_level", 0)
                or 0
            ),
            volume_step=float(
                getattr(info, "volume_step", 0.01)
                or 0.01
            ),
            volume_min=float(
                getattr(info, "volume_min", 0.01)
                or 0.01
            ),
            volume_max=float(
                getattr(info, "volume_max", 100.0)
                or 100.0
            ),
        )

        replay = CycleTheoryHistoricalReplay(
            symbol=args.symbol,
            timeframe=args.timeframe,
            inputs=inputs,
            broker=broker,
            default_spread_points=int(
                getattr(info, "spread", 10)
                or 10
            ),
        )

        bars = replay_bars_from_dataframe(
            dataframe
        )

        result = replay.run(bars, warmup_bars=warmup_bars)
        summary = asdict(result.summary)

        print()
        print("=" * 68)
        print("CYCLE THEORY V111 â€” HISTORICAL REPLAY")
        print("=" * 68)
        print(
            f"{result.symbol} {result.timeframe}"
            f" | evaluation bars: {result.evaluation_bars}"
            f" | warmup bars: {result.warmup_bars}"
        )
        print(
            f"execution model: {result.execution_model}"
        )
        print("-" * 68)
        print(
            f"evaluation start: {result.evaluation_first_time}"
        )
        print(
            f"evaluation end  : {result.evaluation_last_time}"
        )
        print("-" * 68)
        print(
            f"trades: {summary['trades']}"
            f" | wins: {summary['wins']}"
            f" | losses: {summary['losses']}"
            f" | BE: {summary['breakeven']}"
        )
        print(
            f"realized net R: {summary['net_r']:.4f}"
            f" | expectancy: {summary['expectancy_r']:.4f} R"
        )
        print(
            "profit factor R:",
            summary["profit_factor_r"],
        )
        print(
            f"terminal unrealized R: {result.terminal_unrealized_r:.4f}"
            f" | mark-to-market net R: {result.mark_to_market_net_r:.4f}"
        )
        print(
            f"open positions: {result.open_positions}"
            f" | pending: {result.pending_orders}"
        )
        print(
            f"telemetry events: {result.telemetry_events}"
        )
        print("=" * 68)

    finally:
        service.mt5.disconnect()


if __name__ == "__main__":
    main()
