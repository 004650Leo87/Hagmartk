"""Data-boundary helpers for Cycle Theory V111 validation research."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from backend.core.constants import TIMEFRAME_MINUTES

from .historical_replay import ReplayBar
from .time_domain import CycleTheoryBrokerClock


def closed_normalized_candles(
    candles: Iterable[dict[str, Any]],
    timeframe: str,
    now_utc: datetime | None = None,
) -> list[dict[str, Any]]:
    minutes = TIMEFRAME_MINUTES.get(timeframe.upper())
    if minutes is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)

    result: list[dict[str, Any]] = []
    for row in candles:
        opened = datetime.fromisoformat(str(row["time"]).replace("Z", "+00:00"))
        if opened.tzinfo is None:
            raise ValueError("Normalized candle timestamp must be timezone-aware")
        opened = opened.astimezone(timezone.utc)
        if opened + timedelta(minutes=minutes) <= now:
            result.append(dict(row))
    return sorted(result, key=lambda item: item["time"])


def server_replay_bars(
    candles: Iterable[dict[str, Any]],
    clock: CycleTheoryBrokerClock,
) -> list[ReplayBar]:
    result: list[ReplayBar] = []
    for row in candles:
        raw_spread = row.get("spread")
        result.append(
            ReplayBar(
                time=clock.iso_utc_to_server_naive(str(row["time"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                spread_points=int(raw_spread) if raw_spread is not None else None,
            )
        )
    return sorted(result, key=lambda item: item.time)
