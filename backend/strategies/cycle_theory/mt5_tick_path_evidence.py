"""Read-only MT5 evidence for intrabar path and spread fidelity.

This module never sends, modifies, or closes orders. It compares the deterministic
OHLC research path with the observed order of high/low in real MT5 ticks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class TickPathBarEvidence:
    open_time_utc: str
    candle_direction: str
    model_first_extreme: str
    observed_first_extreme: str
    path_matches: bool | None
    ticks: int
    spread_min_points: float
    spread_max_points: float


def model_first_extreme(open_price: float, close_price: float) -> str:
    """Historical replay contract: bullish O-L-H-C, bearish O-H-L-C."""
    return "LOW" if close_price >= open_price else "HIGH"


def observed_first_extreme(ticks: Any, high: float, low: float, tolerance: float) -> str:
    """Return which candle extreme was first reached by observed Bid ticks."""
    first_high = None
    first_low = None
    for index, tick in enumerate(ticks):
        bid = float(tick["bid"])
        if first_high is None and bid >= high - tolerance:
            first_high = index
        if first_low is None and bid <= low + tolerance:
            first_low = index
        if first_high is not None and first_low is not None:
            break
    if first_high is None or first_low is None or first_high == first_low:
        return "UNRESOLVED"
    return "HIGH" if first_high < first_low else "LOW"


def collect_tick_path_evidence(mt5: Any, symbol: str, timeframe: int, bars: int = 30) -> list[TickPathBarEvidence]:
    """Collect recent closed-bar evidence from MT5 using only copy_rates/copy_ticks."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"symbol unavailable: {symbol}")
    point = float(info.point)
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, bars)
    if rates is None:
        raise RuntimeError(f"copy_rates failed: {mt5.last_error()}")

    results: list[TickPathBarEvidence] = []
    ordered = list(reversed(rates))
    for rate in ordered:
        start = datetime.fromtimestamp(int(rate["time"]), timezone.utc)
        end = start + timedelta(minutes=1)
        ticks = mt5.copy_ticks_range(symbol, start, end, mt5.COPY_TICKS_INFO)
        if ticks is None or len(ticks) < 2:
            continue
        high = float(rate["high"])
        low = float(rate["low"])
        observed = observed_first_extreme(ticks, high, low, point * 0.51)
        model = model_first_extreme(float(rate["open"]), float(rate["close"]))
        spreads = [
            (float(t["ask"]) - float(t["bid"])) / point
            for t in ticks
            if float(t["ask"]) > 0 and float(t["bid"]) > 0
        ]
        results.append(TickPathBarEvidence(
            open_time_utc=start.isoformat(),
            candle_direction="BULL" if float(rate["close"]) >= float(rate["open"]) else "BEAR",
            model_first_extreme=model,
            observed_first_extreme=observed,
            path_matches=(None if observed == "UNRESOLVED" else model == observed),
            ticks=len(ticks),
            spread_min_points=round(min(spreads), 4) if spreads else 0.0,
            spread_max_points=round(max(spreads), 4) if spreads else 0.0,
        ))
    return results


def summarize_tick_path_evidence(items: list[TickPathBarEvidence]) -> dict[str, Any]:
    resolved = [item for item in items if item.path_matches is not None]
    matches = sum(1 for item in resolved if item.path_matches)
    return {
        "bars": len(items),
        "resolved": len(resolved),
        "matches": matches,
        "mismatches": len(resolved) - matches,
        "match_rate": round(matches / len(resolved), 4) if resolved else None,
        "total_ticks": sum(item.ticks for item in items),
    }
