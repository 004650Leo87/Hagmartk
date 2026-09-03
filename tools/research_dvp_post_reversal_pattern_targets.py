from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.strategies.hdf.fibonacci_audit import SOURCE_LEVELS, mirrored_extension_levels
from backend.strategies.hdf.prospective_fibonacci import ConfirmedPivot, audit_strict_pre_reversal_leg
from backend.strategies.hdf.strategy import HDFStrategy

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    "USDCAD", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
]
TIMEFRAMES = ["M5", "M15", "M30", "H1", "H2", "H4"]


def level_outcome(df, entry_index, direction, target, stop):
    for k in range(entry_index, len(df)):
        high = float(df.iloc[k].high)
        low = float(df.iloc[k].low)
        target_hit = high >= target if direction == "BULLISH" else low <= target
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        if target_hit and stop_hit:
            return "AMBIGUOUS_SAME_BAR", k - entry_index
        if stop_hit:
            return "STOP_FIRST", k - entry_index
        if target_hit:
            return "TARGET_FIRST", k - entry_index
    return "CENSORED", None


def main():
    rows = []
    adapter = MT5MarketAdapter()
    adapter.connect()
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                df = pd.DataFrame(adapter.get_candles(symbol, timeframe, count=1200))
                strategy = HDFStrategy(variant="HDF_DVP")
                occurrences = strategy.evaluate_full_dataset_analysis(df, symbol, timeframe)["occurrences"]
                highs, lows = strategy.pivot_detector.find_pivots(df)
                pivots = [
                    ConfirmedPivot(p.index, p.price, p.is_high, p.confirmed_at_index, p.time)
                    for p in highs + lows
                ]
                time_to_index = {str(value): i for i, value in enumerate(df.time)}
                for occ in occurrences:
                    decision_index = time_to_index.get(str(occ.temporal_model.confluence_completed_at))
                    p2_index = time_to_index.get(str(occ.temporal_model.pivot_2_time))
                    entry_index = time_to_index.get(str(occ.temporal_model.entry_at)) if occ.temporal_model.entry_at else None
                    if decision_index is None or p2_index is None or entry_index is None or not occ.initial_risk:
                        continue
                    fib = audit_strict_pre_reversal_leg(
                        direction=occ.direction, pivots=pivots, decision_index=decision_index,
                        reversal_pivot_index=p2_index, candle_low=float(df.iloc[decision_index].low),
                        candle_high=float(df.iloc[decision_index].high),
                    )
                    if fib.status != "PASS":
                        continue

                    pattern_low = float(occ.pattern_low)
                    pattern_high = float(occ.pattern_high)
                    if pattern_high <= pattern_low:
                        rows.append((symbol, timeframe, occ.direction, "INVALID_PATTERN", None, None, None))
                        continue

                    anchor_a, anchor_b = (
                        (pattern_low, pattern_high)
                        if occ.direction == "BULLISH"
                        else (pattern_high, pattern_low)
                    )
                    targets = mirrored_extension_levels(anchor_a, anchor_b)
                    entry = float(occ.entry_price)
                    stop = float(occ.initial_stop)

                    for level in SOURCE_LEVELS:
                        target = float(targets[level])
                        ahead = target > entry if occ.direction == "BULLISH" else target < entry
                        if not ahead:
                            rows.append((symbol, timeframe, occ.direction, "BEHIND_ENTRY", level, None, target))
                            continue
                        outcome, bars = level_outcome(df, entry_index, occ.direction, target, stop)
                        rows.append((symbol, timeframe, occ.direction, outcome, level, bars, target))
    finally:
        adapter.disconnect()

    eligible_events = len(rows) // len(SOURCE_LEVELS) if rows else 0
    print("ELIGIBLE_EVENTS", eligible_events)
    print("ROWS", len(rows))
    print("OUTCOME", Counter(row[3] for row in rows))

    by_level = defaultdict(Counter)
    by_timeframe = defaultdict(Counter)
    bars_by_level = defaultdict(list)
    for symbol, timeframe, direction, outcome, level, bars, target in rows:
        if level is not None:
            by_level[level][outcome] += 1
            if bars is not None and outcome == "TARGET_FIRST":
                bars_by_level[level].append(bars)
        by_timeframe[timeframe][outcome] += 1

    for level in SOURCE_LEVELS:
        print("LEVEL", level, dict(by_level[level]))
        values = bars_by_level[level]
        if values:
            print("LEVEL_BARS", level, "MEDIAN", float(pd.Series(values).median()), "MAX", max(values))
    for timeframe in TIMEFRAMES:
        print("TIMEFRAME", timeframe, dict(by_timeframe[timeframe]))


if __name__ == "__main__":
    main()
