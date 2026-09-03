from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.strategies.hdf.fibonacci_audit import mirrored_extension_levels
from backend.strategies.hdf.prospective_fibonacci import ConfirmedPivot, audit_strict_pre_reversal_leg
from backend.strategies.hdf.strategy import HDFStrategy

SNAPSHOT = ROOT / "data_cache" / "dvp_post_reversal_snapshot_20260903.csv"
SYMBOLS = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD"]
TIMEFRAMES = ["M5","M15","M30","H1","H2","H4"]


@dataclass(frozen=True)
class Geometry:
    level: float
    width: float
    entry_displacement: float
    stop_buffer: float
    risk: float
    fib_distance: float
    fib_r: float
    benchmark_distance: float
    benchmark_minus_fib: float


def geometry(*, level: float, width: float, entry_displacement: float, stop_buffer: float) -> Geometry:
    if width <= 0:
        raise ValueError("width must be positive")
    if entry_displacement < 0 or stop_buffer < 0:
        raise ValueError("entry displacement and stop buffer must be non-negative")
    risk = width + entry_displacement + stop_buffer
    fib_distance = level * width - entry_displacement
    benchmark_distance = level * risk
    return Geometry(
        level=level,
        width=width,
        entry_displacement=entry_displacement,
        stop_buffer=stop_buffer,
        risk=risk,
        fib_distance=fib_distance,
        fib_r=fib_distance / risk,
        benchmark_distance=benchmark_distance,
        benchmark_minus_fib=benchmark_distance - fib_distance,
    )


def synthetic_boundary():
    cases = [
        (0.00, 0.00),
        (0.05, 0.00),
        (0.00, 0.05),
        (0.05, 0.05),
        (0.25, 0.00),
        (0.50, 0.25),
        (2.00, 0.00),
    ]
    print("SYNTHETIC_NORMALIZED_W_EQ_1")
    for g, s in cases:
        out = geometry(level=2.0, width=1.0, entry_displacement=g, stop_buffer=s)
        print("CASE", "g", g, "s", s, "FIB200_R", round(out.fib_r, 6), "DELTA_PRICE", round(out.benchmark_minus_fib, 6))


def canonical_snapshot_audit():
    if not SNAPSHOT.exists():
        raise FileNotFoundError(f"frozen snapshot not found: {SNAPSHOT}")
    snapshot_df = pd.read_csv(SNAPSHOT)
    rows = []

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
                if decision_index is None or p2_index is None or not occ.temporal_model.entry_at or not occ.initial_risk:
                    continue
                fib_gate = audit_strict_pre_reversal_leg(
                    direction=occ.direction, pivots=pivots, decision_index=decision_index,
                    reversal_pivot_index=p2_index, candle_low=float(df.iloc[decision_index].low),
                    candle_high=float(df.iloc[decision_index].high),
                )
                if fib_gate.status != "PASS":
                    continue
                width = float(occ.pattern_high) - float(occ.pattern_low)
                if width <= 0:
                    continue
                if occ.direction == "BULLISH":
                    g = float(occ.entry_price) - float(occ.pattern_high)
                    s = float(occ.pattern_low) - float(occ.initial_stop)
                    fib200 = mirrored_extension_levels(float(occ.pattern_low), float(occ.pattern_high))[2.0]
                    benchmark_2r = float(occ.entry_price) + 2.0 * float(occ.initial_risk)
                else:
                    g = float(occ.pattern_low) - float(occ.entry_price)
                    s = float(occ.initial_stop) - float(occ.pattern_high)
                    fib200 = mirrored_extension_levels(float(occ.pattern_high), float(occ.pattern_low))[2.0]
                    benchmark_2r = float(occ.entry_price) - 2.0 * float(occ.initial_risk)

                model = geometry(level=2.0, width=width, entry_displacement=max(0.0, g), stop_buffer=max(0.0, s))
                actual_fib_r = abs(float(fib200) - float(occ.entry_price)) / float(occ.initial_risk)
                actual_delta = abs(float(benchmark_2r) - float(fib200))
                rows.append((symbol,timeframe,occ.direction,width,g,s,actual_fib_r,actual_delta,model.fib_r,model.benchmark_minus_fib))

    frame = pd.DataFrame(rows, columns=["symbol","timeframe","direction","width","g","s","fib200_r","delta_price","model_fib_r","model_delta"])
    print("CANONICAL_EVENTS", len(frame))
    print("NONZERO_G", int((frame.g.abs() > 1e-12).sum()))
    print("NONZERO_S", int((frame.s.abs() > 1e-12).sum()))
    print("EXACT_FIB200_EQ_2R", int(((frame.fib200_r - 2.0).abs() <= 1e-12).sum()))
    print("MAX_MODEL_FIB_R_ERROR", float((frame.fib200_r - frame.model_fib_r).abs().max()))
    print("MAX_MODEL_DELTA_ERROR", float((frame.delta_price - frame.model_delta).abs().max()))
    if len(frame):
        print("FIB200_R_RANGE", float(frame.fib200_r.min()), float(frame.fib200_r.max()))
        print("G_RANGE", float(frame.g.min()), float(frame.g.max()))
        print("S_RANGE", float(frame.s.min()), float(frame.s.max()))


def self_check():
    exact = geometry(level=2.0, width=1.0, entry_displacement=0.0, stop_buffer=0.0)
    assert exact.fib_r == 2.0
    assert exact.benchmark_minus_fib == 0.0
    gap = geometry(level=2.0, width=1.0, entry_displacement=0.1, stop_buffer=0.0)
    assert abs(gap.benchmark_minus_fib - 0.3) < 1e-12
    stop = geometry(level=2.0, width=1.0, entry_displacement=0.0, stop_buffer=0.1)
    assert abs(stop.benchmark_minus_fib - 0.2) < 1e-12
    both = geometry(level=2.0, width=1.0, entry_displacement=0.1, stop_buffer=0.2)
    assert abs(both.benchmark_minus_fib - 0.7) < 1e-12
    assert gap.fib_r < 2.0 and stop.fib_r < 2.0 and both.fib_r < 2.0


def main():
    self_check()
    synthetic_boundary()
    canonical_snapshot_audit()


if __name__ == "__main__":
    main()
