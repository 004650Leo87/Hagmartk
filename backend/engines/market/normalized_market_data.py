from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

REQUIRED_OHLCV_FIELDS = ("time", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class MarketDataProvenance:
    provider: str
    symbol: str
    timeframe: str
    volume_kind: str


@dataclass(frozen=True)
class NormalizedCandle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    provenance: MarketDataProvenance


def normalize_candle(*, candle: Mapping[str, Any], provenance: MarketDataProvenance,
                     volume_field: str) -> NormalizedCandle:
    missing = [key for key in ("time", "open", "high", "low", "close", volume_field) if candle.get(key) is None]
    if missing:
        raise ValueError(f"missing market-data fields: {', '.join(missing)}")
    o, h, l, c = (float(candle[key]) for key in ("open", "high", "low", "close"))
    if h < max(o, c) or l > min(o, c) or h < l:
        raise ValueError("invalid OHLC geometry")
    volume = float(candle[volume_field])
    if volume < 0:
        raise ValueError("volume must be non-negative")
    return NormalizedCandle(
        time=str(candle["time"]), open=o, high=h, low=l, close=c, volume=volume,
        provenance=provenance,
    )


def normalize_series(*, candles: Sequence[Mapping[str, Any]], provenance: MarketDataProvenance,
                     volume_field: str) -> list[NormalizedCandle]:
    return [normalize_candle(candle=c, provenance=provenance, volume_field=volume_field) for c in candles]
