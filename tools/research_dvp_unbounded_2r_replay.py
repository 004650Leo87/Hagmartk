from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.strategies.hdf.strategy import HDFStrategy
from backend.strategies.hdf.prospective_fibonacci import (
    ConfirmedPivot,
    audit_strict_pre_reversal_leg,
)

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
    "USDCAD", "EURJPY", "GBPJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
]
TIMEFRAMES = ["M5", "M15", "M30", "H1", "H2", "H4"]
def outcome_until_data_end(df, entry_index, direction, entry, stop, risk):
    target_2r = entry + 2 * risk if direction == "BULLISH" else entry - 2 * risk
    first_1r = None
    for k in range(entry_index, len(df)):
        high = float(df.iloc[k].high)
        low = float(df.iloc[k].low)
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        hit_1r = high >= entry + risk if direction == "BULLISH" else low <= entry - risk
        hit_2r = high >= target_2r if direction == "BULLISH" else low <= target_2r
        if first_1r is None and hit_1r:
            first_1r = k - entry_index
        if stop_hit and hit_2r:
            return "AMBIGUOUS_SAME_BAR", k - entry_index, first_1r
        if stop_hit:
            return "STOP_FIRST", k - entry_index, first_1r
        if hit_2r:
            return "2R_FIRST", k - entry_index, first_1r
    return "CENSORED", None, first_1r


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
                time_to_index = {str(v): i for i, v in enumerate(df.time)}
                for occ in occurrences:
                    decision_index = time_to_index.get(str(occ.temporal_model.confluence_completed_at))
                    p2_index = time_to_index.get(str(occ.temporal_model.pivot_2_time))
                    entry_index = time_to_index.get(str(occ.temporal_model.entry_at)) if occ.temporal_model.entry_at else None
                    if decision_index is None or p2_index is None or entry_index is None or not occ.initial_risk:
                        continue
                    fib = audit_strict_pre_reversal_leg(
                        direction=occ.direction,
                        pivots=pivots,
                        decision_index=decision_index,
                        reversal_pivot_index=p2_index,
                        candle_low=float(df.iloc[decision_index].low),
                        candle_high=float(df.iloc[decision_index].high),
                    )
                    if fib.status != "PASS":
                        continue
                    outcome, bars, first_1r = outcome_until_data_end(
                        df, entry_index, occ.direction, float(occ.entry_price),
                        float(occ.initial_stop), float(occ.initial_risk),
                    )
                    rows.append((symbol, timeframe, occ.direction, outcome, bars, first_1r, len(df) - 1 - entry_index))
    finally:
        adapter.disconnect()

    print("N", len(rows))
    print("OUTCOME", Counter(row[3] for row in rows))
    resolved = [row[4] for row in rows if row[4] is not None]
    print("MEDIAN_BARS", pd.Series(resolved).median() if resolved else None)
    print("MAX_BARS", max(resolved) if resolved else None)
    print("CENSORED", [row for row in rows if row[3] == "CENSORED"])
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
