from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
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
SNAPSHOT = ROOT / "data_cache" / "dvp_post_reversal_snapshot_20260903.csv"
META = ROOT / "data_cache" / "dvp_post_reversal_snapshot_20260903_meta.json"


def level_outcome(df, entry_index, direction, target, stop):
    for k in range(entry_index, len(df)):
        high, low = float(df.iloc[k].high), float(df.iloc[k].low)
        target_hit = high >= target if direction == "BULLISH" else low <= target
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        if target_hit and stop_hit:
            return "AMBIGUOUS_SAME_BAR", k - entry_index
        if stop_hit:
            return "STOP_FIRST", k - entry_index
        if target_hit:
            return "TARGET_FIRST", k - entry_index
    return "CENSORED", None


def capture_snapshot():
    adapter = MT5MarketAdapter()
    frames = []
    adapter.connect()
    try:
        for symbol in SYMBOLS:
            for timeframe in TIMEFRAMES:
                df = pd.DataFrame(adapter.get_candles(symbol, timeframe, count=1200))
                local = df.copy()
                local.insert(0, "snapshot_symbol", symbol)
                local.insert(1, "snapshot_timeframe", timeframe)
                frames.append(local)
    finally:
        adapter.disconnect()

    snapshot_df = pd.concat(frames, ignore_index=True)
    snapshot_df.to_csv(SNAPSHOT, index=False)
    META.write_text(json.dumps({
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": SYMBOLS,
        "timeframes": TIMEFRAMES,
        "requested_candles_per_pair": 1200,
        "rows": len(snapshot_df),
    }, indent=2), encoding="utf-8")
    return snapshot_df, "CAPTURED"


def load_snapshot(refresh=False):
    if refresh or not SNAPSHOT.exists():
        return capture_snapshot()
    snapshot_df = pd.read_csv(SNAPSHOT)
    return snapshot_df, "REUSED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="capture a new rolling MT5 snapshot")
    args = parser.parse_args()

    snapshot_df, snapshot_mode = load_snapshot(refresh=args.refresh)
    rows = []
    eligible_events = 0

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            df = snapshot_df[(snapshot_df.snapshot_symbol == symbol) & (snapshot_df.snapshot_timeframe == timeframe)].copy()
            df = df.drop(columns=["snapshot_symbol", "snapshot_timeframe"]).reset_index(drop=True)
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
                eligible_events += 1
                anchor_a, anchor_b = ((pattern_low, pattern_high) if occ.direction == "BULLISH" else (pattern_high, pattern_low))
                targets = mirrored_extension_levels(anchor_a, anchor_b)
                entry, stop, risk = float(occ.entry_price), float(occ.initial_stop), float(occ.initial_risk)
                for level in SOURCE_LEVELS:
                    target = float(targets[level])
                    ahead = target > entry if occ.direction == "BULLISH" else target < entry
                    if not ahead:
                        rows.append((symbol,timeframe,level,"BEHIND_ENTRY",None,None))
                        continue
                    outcome, bars = level_outcome(df, entry_index, occ.direction, target, stop)
                    target_r = abs(target - entry) / risk
                    rows.append((symbol,timeframe,level,outcome,bars,target_r))

    print("SNAPSHOT_MODE", snapshot_mode)
    print("SNAPSHOT", SNAPSHOT)
    print("SNAPSHOT_ROWS", len(snapshot_df))
    print("ELIGIBLE_EVENTS", eligible_events)
    print("ROWS", len(rows))
    print("OUTCOME", Counter(row[3] for row in rows))

    by_level = defaultdict(Counter)
    r_by_level = defaultdict(list)
    bars_by_level = defaultdict(list)
    for _, _, level, outcome, bars, target_r in rows:
        by_level[level][outcome] += 1
        if target_r is not None:
            r_by_level[level].append(target_r)
        if bars is not None and outcome == "TARGET_FIRST":
            bars_by_level[level].append(bars)

    for level in SOURCE_LEVELS:
        r_series = pd.Series(r_by_level[level], dtype=float)
        b_series = pd.Series(bars_by_level[level], dtype=float)
        print(
            "LEVEL", level,
            dict(by_level[level]),
            "R_MEDIAN", round(float(r_series.median()), 4) if not r_series.empty else None,
            "R_MIN", round(float(r_series.min()), 4) if not r_series.empty else None,
            "R_MAX", round(float(r_series.max()), 4) if not r_series.empty else None,
            "TARGET_BARS_MEDIAN", round(float(b_series.median()), 2) if not b_series.empty else None,
            "TARGET_BARS_MAX", int(b_series.max()) if not b_series.empty else None,
        )


if __name__ == "__main__":
    main()
