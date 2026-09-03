from __future__ import annotations

from collections import defaultdict
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

SYMBOLS = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD"]
TIMEFRAMES = ["M5","M15","M30","H1","H2","H4"]


def main():
    values = defaultdict(list)
    event_count = 0
    adapter = MT5MarketAdapter()
    adapter.connect()
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                df = pd.DataFrame(adapter.get_candles(symbol, timeframe, count=1200))
                strategy = HDFStrategy(variant="HDF_DVP")
                occurrences = strategy.evaluate_full_dataset_analysis(df, symbol, timeframe)["occurrences"]
                highs, lows = strategy.pivot_detector.find_pivots(df)
                pivots = [ConfirmedPivot(p.index,p.price,p.is_high,p.confirmed_at_index,p.time) for p in highs+lows]
                time_to_index = {str(v): i for i, v in enumerate(df.time)}
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
                    pattern_low, pattern_high = float(occ.pattern_low), float(occ.pattern_high)
                    if pattern_high <= pattern_low:
                        continue
                    event_count += 1
                    anchor_a, anchor_b = ((pattern_low, pattern_high) if occ.direction == "BULLISH" else (pattern_high, pattern_low))
                    targets = mirrored_extension_levels(anchor_a, anchor_b)
                    entry = float(occ.entry_price)
                    risk = float(occ.initial_risk)
                    for level in SOURCE_LEVELS:
                        target = float(targets[level])
                        target_r = abs(target - entry) / risk
                        values[level].append(target_r)
    finally:
        adapter.disconnect()

    print("ELIGIBLE_EVENTS", event_count)
    for level in SOURCE_LEVELS:
        series = pd.Series(values[level], dtype=float)
        print(
            "LEVEL_R", level,
            "N", len(series),
            "MIN", round(float(series.min()), 4),
            "Q1", round(float(series.quantile(0.25)), 4),
            "MEDIAN", round(float(series.median()), 4),
            "Q3", round(float(series.quantile(0.75)), 4),
            "MAX", round(float(series.max()), 4),
            "MEAN", round(float(series.mean()), 4),
            "LT_1R", int((series < 1.0).sum()),
            "GE_2R", int((series >= 2.0).sum()),
        )


if __name__ == "__main__":
    main()
