from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_data import (
    closed_normalized_candles,
    server_replay_bars,
)
from backend.strategies.cycle_theory.validation_candidate import (
    CYCLE_THEORY_V111_BASELINE,
    CYCLE_THEORY_V111_BASELINE_HASH,
)


DEFAULT_SYMBOLS = (
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "USDCAD", "NZDUSD",
    "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
)
DEFAULT_TIMEFRAMES = ("M5", "M15", "M30", "H1", "H2", "H4")


def _split_csv(value: str) -> list[str]:
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _broker_for(symbol: str) -> MockBroker:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Symbol not available: {symbol}")
    return MockBroker(
        symbol=symbol,
        point=float(info.point),
        digits=int(info.digits),
        stops_level_pts=int(getattr(info, "trade_stops_level", 0) or 0),
        freeze_level_pts=int(getattr(info, "trade_freeze_level", 0) or 0),
        volume_step=float(getattr(info, "volume_step", 0.01) or 0.01),
        volume_min=float(getattr(info, "volume_min", 0.01) or 0.01),
        volume_max=float(getattr(info, "volume_max", 100.0) or 100.0),
    )


def _screen_one(adapter, clock, symbol: str, timeframe: str, bars_count: int, offset: int = 0) -> dict:
    inputs = baseline_inputs()
    warmup = max(5, inputs.atr_period)
    candles = adapter.get_candles(symbol, timeframe, count=bars_count + warmup + offset + 2)
    candles = closed_normalized_candles(candles, timeframe)
    if offset:
        candles = candles[:-offset]
    candles = candles[-(bars_count + warmup):]
    if len(candles) < bars_count + warmup:
        raise RuntimeError("Insufficient closed candles for screening window")
    bars = server_replay_bars(candles, clock)
    broker = _broker_for(symbol)
    info = mt5.symbol_info(symbol)
    replay = CycleTheoryHistoricalReplay(
        symbol=symbol,
        timeframe=timeframe,
        inputs=inputs,
        broker=broker,
        default_spread_points=int(getattr(info, "spread", 10) or 10),
    )
    result = replay.run(bars, warmup_bars=warmup)
    summary = asdict(result.summary)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "bars": result.evaluation_bars,
        "start": str(result.evaluation_first_time or ""),
        "end": str(result.evaluation_last_time or ""),
        "trades": summary["trades"],
        "wins": summary["wins"],
        "losses": summary["losses"],
        "breakeven": summary["breakeven"],
        "net_r": summary["net_r"],
        "expectancy_r": summary["expectancy_r"],
        "profit_factor_r": summary["profit_factor_r"],
        "mark_to_market_net_r": result.mark_to_market_net_r,
        "open_positions": result.open_positions,
        "pending_orders": result.pending_orders,
        "execution_model": result.execution_model,
        "cost_model": result.cost_model,
        "fill_model": result.fill_model,
        "status": "OK",
        "error": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Cycle Theory V111 research screening matrix")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES))
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()

    symbols = _split_csv(args.symbols)
    timeframes = _split_csv(args.timeframes)
    if args.bars <= 0:
        raise ValueError("--bars must be greater than zero")
    if not symbols or not timeframes:
        raise ValueError("At least one symbol and timeframe are required")

    adapter = MT5MarketAdapter()
    adapter.connect()
    scope = adapter.get_runtime_scope()
    clock = CycleTheoryBrokerClock.from_runtime_scope(scope)
    rows: list[dict] = []

    try:
        total = len(symbols) * len(timeframes)
        index = 0
        for symbol in symbols:
            for timeframe in timeframes:
                index += 1
                try:
                    row = _screen_one(adapter, clock, symbol, timeframe, args.bars)
                    rows.append(row)
                    print(
                        f"[{index:02d}/{total}] {symbol} {timeframe} "
                        f"trades={row['trades']} netR={row['net_r']:.3f} "
                        f"exp={row['expectancy_r']:.3f}"
                    )
                except Exception as exc:
                    row = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bars": 0,
                        "trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "breakeven": 0,
                        "net_r": 0.0,
                        "expectancy_r": 0.0,
                        "profit_factor_r": None,
                        "status": "ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    rows.append(row)
                    print(f"[{index:02d}/{total}] {symbol} {timeframe} ERROR: {exc}")
    finally:
        adapter.disconnect()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = output_dir / f"cycle_theory_v111_screening_{stamp}"
    csv_path = base.with_suffix(".csv")
    json_path = base.with_suffix(".json")

    fieldnames = sorted({key for row in rows for key in row.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "strategy": "cycle_theory_v111_fidelity",
        "source_version": "111.00",
        "candidate_id": CYCLE_THEORY_V111_BASELINE.candidate_id,
        "candidate_version": CYCLE_THEORY_V111_BASELINE.candidate_version,
        "parameter_hash": CYCLE_THEORY_V111_BASELINE_HASH,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_server": scope.get("server"),
        "clock_policy": clock.metadata(),
        "bars_per_combination": args.bars,
        "symbols": symbols,
        "timeframes": timeframes,
        "execution_boundary": {
            "execution_model": "OHLC_PATH_V0",
            "cost_model": "ZERO_COMMISSION_ZERO_SWAP",
            "fill_model": "OHLC_PATH_IDEALIZED_NO_SLIPPAGE",
            "profitability_claim_allowed": False,
            "real_order_execution": False,
        },
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    ok_rows = [row for row in rows if row.get("status") == "OK"]
    trade_rows = [row for row in ok_rows if int(row.get("trades", 0)) > 0]
    print("-" * 72)
    print(f"completed={len(ok_rows)}/{len(rows)} | with_trades={len(trade_rows)}")
    print(f"csv={csv_path}")
    print(f"json={json_path}")
    print(
        "BOUNDARY: screening only. Rankings from this file are not "
        "broker-faithful performance or proof of profit."
    )


if __name__ == "__main__":
    main()
