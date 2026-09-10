from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Literal

Direction = Literal["UP", "DOWN"]


@dataclass(frozen=True)
class OpeningChannel:
    start: datetime
    end: datetime
    low: float
    high: float

    @property
    def height(self) -> float:
        return self.high - self.low


@dataclass(frozen=True)
class CycleBand:
    name: str
    low: float
    high: float
    size: float
    midpoint: float


@dataclass(frozen=True)
class PublicCycleGeometry:
    opening_channel: OpeningChannel
    direction: Direction
    cycles: tuple[CycleBand, ...]
    confidence: str = "REFERENCE_ONLY_SECONDARY_GEOMETRY"

def _aware_time(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("M15 bar time must be timezone-aware")
    return parsed


def build_opening_channel(rows: Iterable[dict[str, Any]]) -> OpeningChannel:
    bars = sorted((dict(row) for row in rows), key=lambda row: _aware_time(row["time"]))
    if len(bars) < 4:
        raise ValueError("Opening channel requires four closed M15 bars")
    bars = bars[:4]
    times = [_aware_time(row["time"]) for row in bars]
    for previous, current in zip(times, times[1:]):
        if current - previous != timedelta(minutes=15):
            raise ValueError("Opening M15 bars must be contiguous")
    lows = [float(row["low"]) for row in bars]
    highs = [float(row["high"]) for row in bars]
    low, high = min(lows), max(highs)
    if high <= low:
        raise ValueError("Opening channel must have positive height")
    return OpeningChannel(
        start=times[0], end=times[-1] + timedelta(minutes=15), low=low, high=high,
    )

def project_accumulated_cycles(
    channel: OpeningChannel,
    direction: Direction,
    count: int = 3,
) -> PublicCycleGeometry:
    if direction not in {"UP", "DOWN"}:
        raise ValueError("Direction must be UP or DOWN")
    if count < 1 or count > 8:
        raise ValueError("Cycle count must be between 1 and 8")
    previous_sizes = [channel.height]
    anchor = channel.high if direction == "UP" else channel.low
    cycles: list[CycleBand] = []
    for index in range(1, count + 1):
        size = channel.height if index == 1 else sum(previous_sizes)
        if direction == "UP":
            low, high = anchor, anchor + size
            anchor = high
        else:
            low, high = anchor - size, anchor
            anchor = low
        cycles.append(CycleBand(
            name=f"C{index}", low=low, high=high, size=size,
            midpoint=(low + high) / 2.0,
        ))
        previous_sizes.append(size)
    return PublicCycleGeometry(channel, direction, tuple(cycles))


def detect_first_breakout_close(
    channel: OpeningChannel,
    rows_after_channel: Iterable[dict[str, Any]],
) -> Direction | None:
    for row in sorted((dict(row) for row in rows_after_channel), key=lambda item: _aware_time(item["time"])):
        close = float(row["close"])
        if close > channel.high:
            return "UP"
        if close < channel.low:
            return "DOWN"
    return None