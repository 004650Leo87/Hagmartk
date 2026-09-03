from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.strategies.hdf.fibonacci_audit import SOURCE_LEVELS
from backend.strategies.hdf.strategy import HDFStrategy
from tools.research_dvp_htf_fibonacci_context import (
    SYMBOLS,
    frame_for,
    load_snapshot,
    qualified_h4_events,
)


def first_parent_terminal(m15, start_index, direction, stop, target):
    for k in range(start_index, len(m15)):
        high, low = float(m15.iloc[k].high), float(m15.iloc[k].low)
        target_hit = low <= target <= high
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        if target_hit and stop_hit:
            return "AMBIGUOUS_SAME_BAR", k
        if stop_hit:
            return "STOP_FIRST", k
        if target_hit:
            return "TARGET_FIRST", k
    return "CENSORED", None


def distance_to_range(target, low, high):
    if low <= target <= high:
        return 0.0
    if target < low:
        return low - target
    return target - high


def main():
    snapshot_df, snapshot_mode = load_snapshot(refresh=False)
    terminals = Counter()
    rows = []

    for symbol in SYMBOLS:
        h4 = frame_for(snapshot_df, symbol, "H4")
        m15 = frame_for(snapshot_df, symbol, "M15")
        parents = qualified_h4_events(h4, symbol)
        if not parents:
            continue

        strategy = HDFStrategy(variant="HDF_DVP")
        children = strategy.evaluate_full_dataset_analysis(m15, symbol, "M15")["occurrences"]
        m15_times = pd.to_datetime(m15.time, utc=True)
        time_to_index = {str(v): i for i, v in enumerate(m15.time)}

        child_rows = []
        for child in children:
            idx = time_to_index.get(str(child.temporal_model.confluence_completed_at))
            if idx is not None:
                child_rows.append((idx, child))
        for parent, levels in parents:
            parent_time = pd.to_datetime(parent.temporal_model.entry_at, utc=True)
            start_index = int(m15_times.searchsorted(parent_time, side="left"))
            if start_index >= len(m15):
                continue

            for level in SOURCE_LEVELS:
                target = float(levels[level])
                state, terminal_index = first_parent_terminal(
                    m15,
                    start_index,
                    parent.direction,
                    float(parent.initial_stop),
                    target,
                )
                terminals[state] += 1
                if state != "TARGET_FIRST" or terminal_index is None:
                    continue

                opposite = [
                    (idx, child) for idx, child in child_rows
                    if idx >= terminal_index and child.direction != parent.direction
                ]
                if not opposite:
                    rows.append((symbol,parent.direction,level,terminal_index,None,None,None,None,None))
                    continue

                child_index, child = opposite[0]
                lag = child_index - terminal_index
                child_low = float(m15.iloc[child_index].low)
                child_high = float(m15.iloc[child_index].high)
                gap = distance_to_range(target, child_low, child_high)
                gap_r = gap / float(parent.initial_risk) if parent.initial_risk else None
                rows.append((
                    symbol,
                    parent.direction,
                    level,
                    terminal_index,
                    child_index,
                    child.direction,
                    lag,
                    gap_r,
                    child.occurrence_id,
                ))

    print("SNAPSHOT_MODE", snapshot_mode)
    print("PARENT_TARGET_TERMINALS", dict(terminals))
    print("TARGET_FIRST_LEVELS", sum(1 for row in rows))
    with_child = [row for row in rows if row[4] is not None]
    print("TARGET_FIRST_WITH_OPPOSITE_CHILD", len(with_child))

    if with_child:
        lags = pd.Series([row[6] for row in with_child], dtype=float)
        gaps = pd.Series([row[7] for row in with_child], dtype=float)
        print("LAG_BARS_MIN", int(lags.min()))
        print("LAG_BARS_Q1", float(lags.quantile(0.25)))
        print("LAG_BARS_MEDIAN", float(lags.median()))
        print("LAG_BARS_Q3", float(lags.quantile(0.75)))
        print("LAG_BARS_MAX", int(lags.max()))
        print("CHILD_RANGE_GAP_R_MIN", round(float(gaps.min()), 6))
        print("CHILD_RANGE_GAP_R_MEDIAN", round(float(gaps.median()), 6))
        print("CHILD_RANGE_GAP_R_MAX", round(float(gaps.max()), 6))
    for row in rows:
        print("ROW", row)


if __name__ == "__main__":
    main()
