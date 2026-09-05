from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.engines.market.mt5_market_adapter import MT5MarketAdapter
from backend.run_cycle_theory_screening import _screen_one
from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_candidate import (
    CYCLE_THEORY_V111_BASELINE,
    CYCLE_THEORY_V111_BASELINE_HASH,
)


def _offsets(value: str) -> list[int]:
    offsets = [int(item.strip()) for item in value.split(",") if item.strip()]
    if any(item < 0 for item in offsets):
        raise ValueError("Offsets cannot be negative")
    return offsets


def _select_pairs(
    screening_csv: str,
    min_trades: int,
    min_expectancy: float,
    top_n: int,
) -> list[tuple[str, str]]:
    frame = pd.read_csv(screening_csv)
    required = {"symbol", "timeframe", "trades", "expectancy_r", "status"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Screening CSV missing columns: {sorted(missing)}")
    eligible = frame[
        (frame["status"] == "OK")
        & (frame["trades"] >= min_trades)
        & (frame["expectancy_r"] >= min_expectancy)
    ].copy()
    eligible = eligible.sort_values(
        ["expectancy_r", "trades"], ascending=[False, False]
    ).head(top_n)
    return list(zip(eligible["symbol"], eligible["timeframe"]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cycle Theory V111 multi-window stability research"
    )
    parser.add_argument("screening_csv")
    parser.add_argument("--bars", type=int, default=1500)
    parser.add_argument("--offsets", default="0,1500,3000")
    parser.add_argument("--min-trades", type=int, default=15)
    parser.add_argument("--min-expectancy", type=float, default=0.15)
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--output-dir", default="artifacts")
    args = parser.parse_args()

    if args.bars <= 0:
        raise ValueError("--bars must be greater than zero")
    offsets = _offsets(args.offsets)
    pairs = _select_pairs(
        args.screening_csv,
        args.min_trades,
        args.min_expectancy,
        args.top_n,
    )
    if not pairs:
        raise RuntimeError("No screening pairs met the research filter")

    adapter = MT5MarketAdapter()
    adapter.connect()
    scope = adapter.get_runtime_scope()
    clock = CycleTheoryBrokerClock.from_runtime_scope(scope)
    rows: list[dict] = []

    try:
        total = len(pairs) * len(offsets)
        index = 0
        for symbol, timeframe in pairs:
            for offset in offsets:
                index += 1
                try:
                    row = _screen_one(
                        adapter, clock, symbol, timeframe, args.bars, offset=offset
                    )
                    row["offset"] = offset
                    rows.append(row)
                    print(
                        f"[{index:02d}/{total}] {symbol} {timeframe} offset={offset} "
                        f"trades={row['trades']} netR={row['net_r']:.3f} "
                        f"exp={row['expectancy_r']:.3f}",
                        flush=True,
                    )
                except Exception as exc:
                    rows.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "offset": offset,
                        "bars": 0,
                        "trades": 0,
                        "net_r": 0.0,
                        "expectancy_r": 0.0,
                        "profit_factor_r": None,
                        "status": "ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    print(
                        f"[{index:02d}/{total}] {symbol} {timeframe} "
                        f"offset={offset} ERROR: {exc}",
                        flush=True,
                    )
    finally:
        adapter.disconnect()

    frame = pd.DataFrame(rows)
    ok = frame[frame["status"] == "OK"].copy()
    summary_rows: list[dict] = []
    for (symbol, timeframe), group in ok.groupby(["symbol", "timeframe"]):
        expected_windows = len(offsets)
        windows = len(group)
        positive_windows = int((group["expectancy_r"] > 0).sum())
        total_trades = int(group["trades"].sum())
        weighted_exp = (
            float((group["expectancy_r"] * group["trades"]).sum() / total_trades)
            if total_trades > 0 else 0.0
        )
        summary_rows.append({
            "symbol": symbol,
            "timeframe": timeframe,
            "windows": windows,
            "expected_windows": expected_windows,
            "positive_windows": positive_windows,
            "positive_window_ratio": positive_windows / expected_windows,
            "total_trades": total_trades,
            "total_net_r": float(group["net_r"].sum()),
            "weighted_expectancy_r": weighted_exp,
            "median_expectancy_r": float(group["expectancy_r"].median()),
            "worst_expectancy_r": float(group["expectancy_r"].min()),
            "best_expectancy_r": float(group["expectancy_r"].max()),
        })

    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["positive_window_ratio", "weighted_expectancy_r", "total_trades"],
            ascending=[False, False, False],
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    detail_csv = output_dir / f"cycle_theory_v111_stability_detail_{stamp}.csv"
    summary_csv = output_dir / f"cycle_theory_v111_stability_summary_{stamp}.csv"
    json_path = output_dir / f"cycle_theory_v111_stability_{stamp}.json"
    frame.to_csv(detail_csv, index=False)
    summary.to_csv(summary_csv, index=False)

    payload = {
        "strategy": "cycle_theory_v111_fidelity",
        "candidate_id": CYCLE_THEORY_V111_BASELINE.candidate_id,
        "candidate_version": CYCLE_THEORY_V111_BASELINE.candidate_version,
        "parameter_hash": CYCLE_THEORY_V111_BASELINE_HASH,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_server": scope.get("server"),
        "bars_per_window": args.bars,
        "offsets": offsets,
        "screening_filter": {
            "min_trades": args.min_trades,
            "min_expectancy_r": args.min_expectancy,
            "top_n": args.top_n,
        },
        "execution_boundary": {
            "execution_model": "OHLC_PATH_V0",
            "profitability_claim_allowed": False,
            "real_order_execution": False,
        },
        "details": frame.to_dict("records"),
        "summary": summary.to_dict("records"),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    print("-" * 72)
    print(summary.to_string(index=False))
    print("-" * 72)
    print(f"detail_csv={detail_csv}")
    print(f"summary_csv={summary_csv}")
    print(f"json={json_path}")
    print(
        "BOUNDARY: multi-window stability is research evidence only; "
        "tick-backed execution validation is still required."
    )


if __name__ == "__main__":
    main()
