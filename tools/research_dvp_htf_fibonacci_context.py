from __future__ import annotations

from collections import Counter
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
SNAPSHOT = ROOT / "data_cache" / "dvp_htf_h4_m15_snapshot_20260903.csv"
META = ROOT / "data_cache" / "dvp_htf_h4_m15_snapshot_20260903_meta.json"


def parse_utc(value):
    ts = pd.to_datetime(value, utc=True)
    return ts.to_pydatetime()


def capture_snapshot():
    adapter = MT5MarketAdapter()
    frames = []
    meta_rows = []
    adapter.connect()
    try:
        for symbol in SYMBOLS:
            h4 = pd.DataFrame(adapter.get_candles(symbol, "H4", count=1200))
            start = parse_utc(h4.iloc[0].time)
            end = parse_utc(h4.iloc[-1].time)
            m15 = pd.DataFrame(adapter.get_candles(symbol, "M15", from_time=start, to_time=end))

            for timeframe, df in (("H4", h4), ("M15", m15)):
                local = df.copy()
                local.insert(0, "snapshot_symbol", symbol)
                local.insert(1, "snapshot_timeframe", timeframe)
                frames.append(local)

            meta_rows.append({
                "symbol": symbol,
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "h4_rows": len(h4),
                "m15_rows": len(m15),
            })
    finally:
        adapter.disconnect()
    snapshot_df = pd.concat(frames, ignore_index=True)
    snapshot_df.to_csv(SNAPSHOT, index=False)
    META.write_text(json.dumps({
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "H4_1200_BARS_WITH_M15_SAME_UTC_RANGE",
        "symbols": meta_rows,
        "rows": len(snapshot_df),
    }, indent=2), encoding="utf-8")
    return snapshot_df, "CAPTURED"


def load_snapshot(refresh=False):
    if refresh or not SNAPSHOT.exists():
        return capture_snapshot()
    return pd.read_csv(SNAPSHOT), "REUSED"


def frame_for(snapshot_df, symbol, timeframe):
    out = snapshot_df[(snapshot_df.snapshot_symbol == symbol) & (snapshot_df.snapshot_timeframe == timeframe)].copy()
    return out.drop(columns=["snapshot_symbol", "snapshot_timeframe"]).reset_index(drop=True)


def confirmed_pivots(strategy, df):
    highs, lows = strategy.pivot_detector.find_pivots(df)
    return [ConfirmedPivot(p.index,p.price,p.is_high,p.confirmed_at_index,p.time) for p in highs+lows]


def qualified_h4_events(df, symbol):
    strategy = HDFStrategy(variant="HDF_DVP")
    occurrences = strategy.evaluate_full_dataset_analysis(df, symbol, "H4")["occurrences"]
    pivots = confirmed_pivots(strategy, df)
    time_to_index = {str(v): i for i, v in enumerate(df.time)}
    parents = []
    for occ in occurrences:
        decision_index = time_to_index.get(str(occ.temporal_model.confluence_completed_at))
        p2_index = time_to_index.get(str(occ.temporal_model.pivot_2_time))
        if decision_index is None or p2_index is None or not occ.temporal_model.entry_at or not occ.initial_risk:
            continue
        fib = audit_strict_pre_reversal_leg(
            direction=occ.direction, pivots=pivots, decision_index=decision_index,
            reversal_pivot_index=p2_index, candle_low=float(df.iloc[decision_index].low),
            candle_high=float(df.iloc[decision_index].high),
        )
        if fib.status != "PASS" or float(occ.pattern_high) <= float(occ.pattern_low):
            continue
        anchor_a, anchor_b = (
            (float(occ.pattern_low), float(occ.pattern_high))
            if occ.direction == "BULLISH"
            else (float(occ.pattern_high), float(occ.pattern_low))
        )
        parents.append((occ, mirrored_extension_levels(anchor_a, anchor_b)))
    return parents


def inspect_parent_level(m15, start_index, child_index, direction, stop, target):
    for k in range(start_index, child_index):
        high, low = float(m15.iloc[k].high), float(m15.iloc[k].low)
        target_hit = low <= target <= high
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        if target_hit and stop_hit:
            return "AMBIGUOUS_TARGET_STOP_PRIOR_BAR"
        if target_hit:
            return "PRIOR_TARGET_CONTACT"
        if stop_hit:
            return "PARENT_STOPPED"

    high, low = float(m15.iloc[child_index].high), float(m15.iloc[child_index].low)
    target_hit = low <= target <= high
    stop_hit = low <= stop if direction == "BULLISH" else high >= stop
    if target_hit and stop_hit:
        return "AMBIGUOUS_TARGET_STOP_CHILD_BAR"
    if target_hit:
        return "MATCH"
    if stop_hit:
        return "PARENT_STOP_ON_CHILD_BAR"
    return "NO_CONTACT"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="capture a new aligned H4/M15 snapshot")
    args = parser.parse_args()

    snapshot_df, snapshot_mode = load_snapshot(refresh=args.refresh)
    matches = []
    diagnostics = Counter()
    parent_count = 0
    child_count = 0
    parent_by_symbol = Counter()
    child_by_symbol = Counter()

    for symbol in SYMBOLS:
        h4 = frame_for(snapshot_df, symbol, "H4")
        m15 = frame_for(snapshot_df, symbol, "M15")
        parents = qualified_h4_events(h4, symbol)
        parent_count += len(parents)
        parent_by_symbol[symbol] += len(parents)

        m15_strategy = HDFStrategy(variant="HDF_DVP")
        children = m15_strategy.evaluate_full_dataset_analysis(m15, symbol, "M15")["occurrences"]
        child_count += len(children)
        child_by_symbol[symbol] += len(children)
        m15_times = pd.to_datetime(m15.time, utc=True)
        m15_time_to_index = {str(v): i for i, v in enumerate(m15.time)}
        for child in children:
            child_index = m15_time_to_index.get(str(child.temporal_model.confluence_completed_at))
            if child_index is None:
                diagnostics["CHILD_INDEX_UNRESOLVED"] += 1
                continue
            child_time = m15_times.iloc[child_index]

            for parent, levels in parents:
                if parent.direction == child.direction:
                    diagnostics["SAME_DIRECTION_PARENT"] += 1
                    continue
                parent_time = pd.to_datetime(parent.temporal_model.entry_at, utc=True)
                if parent_time >= child_time:
                    diagnostics["PARENT_NOT_PRIOR"] += 1
                    continue
                start_index = int(m15_times.searchsorted(parent_time, side="left"))
                if start_index >= child_index:
                    diagnostics["NO_M15_LIFECYCLE_WINDOW"] += 1
                    continue

                for level in SOURCE_LEVELS:
                    target = float(levels[level])
                    status = inspect_parent_level(
                        m15, start_index, child_index, parent.direction,
                        float(parent.initial_stop), target,
                    )
                    diagnostics[status] += 1
                    if status != "MATCH":
                        continue
                    matches.append((
                        symbol,
                        str(parent.temporal_model.entry_at),
                        parent.direction,
                        str(child.temporal_model.confluence_completed_at),
                        child.direction,
                        float(level),
                        target,
                        parent.occurrence_id,
                        child.occurrence_id,
                    ))

    print("SNAPSHOT_MODE", snapshot_mode)
    print("SNAPSHOT_ROWS", len(snapshot_df))
    print("PARENT_H4_QUALIFIED", parent_count)
    print("CHILD_M15_DVP", child_count)
    print("PARENTS_BY_SYMBOL", dict(parent_by_symbol))
    print("CHILDREN_BY_SYMBOL", dict(child_by_symbol))
    print("DIAGNOSTICS", dict(diagnostics))
    print("RAW_MATCHES", len(matches))
    unique_children = {row[8] for row in matches}
    print("UNIQUE_CHILD_MATCHES", len(unique_children))
    print("MATCH_LEVELS", dict(Counter(row[5] for row in matches)))
    print("MATCH_SYMBOLS", dict(Counter(row[0] for row in matches)))
    multiplicity = Counter(row[8] for row in matches)
    print("CHILD_MULTIPLICITY", dict(Counter(multiplicity.values())))
    for row in matches:
        print("MATCH", row)


if __name__ == "__main__":
    main()
