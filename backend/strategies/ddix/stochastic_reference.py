from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, Tuple

DDIX_STOCHASTIC_K_PERIOD_CANDIDATE = 8
DDIX_STOCHASTIC_D_PERIOD_CANDIDATE = 3
DDIX_STOCHASTIC_SLOWING_CANDIDATE = 3
DDIX_STOCHASTIC_OVERBOUGHT = 80.0
DDIX_STOCHASTIC_OVERSOLD = 20.0


@dataclass(frozen=True)
class StochasticPoint:
    index: int
    k: float
    d: float | None
    zone: str
    provenance: str


@dataclass(frozen=True)
class StochasticCrossEvidence:
    previous: StochasticPoint
    current: StochasticPoint
    bullish_cross: bool
    bearish_cross: bool
    line_bias: str
    extreme_is_not_reversal_signal: bool
    reason_codes: Tuple[str, ...]
    provenance: str


def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_STOCHASTIC_VALUE_NOT_FINITE")
    return number


def _validate_ohlc(
    highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    if not highs or not lows or not closes:
        raise ValueError("DDIX_STOCHASTIC_EMPTY_SERIES")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("DDIX_STOCHASTIC_LENGTH_MISMATCH")
    h = tuple(_finite(v) for v in highs)
    l = tuple(_finite(v) for v in lows)
    c = tuple(_finite(v) for v in closes)
    for hi, lo, close in zip(h, l, c):
        if hi < lo or close > hi or close < lo:
            raise ValueError("DDIX_STOCHASTIC_INVALID_OHLC")
    return h, l, c


def _zone(value: float) -> str:
    if value >= DDIX_STOCHASTIC_OVERBOUGHT:
        return "OVERBOUGHT"
    if value <= DDIX_STOCHASTIC_OVERSOLD:
        return "OVERSOLD"
    return "NEUTRAL"


def compute_slow_stochastic(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    k_period: int = DDIX_STOCHASTIC_K_PERIOD_CANDIDATE,
    d_period: int = DDIX_STOCHASTIC_D_PERIOD_CANDIDATE,
    slowing: int = DDIX_STOCHASTIC_SLOWING_CANDIDATE,
) -> tuple[StochasticPoint, ...]:
    if k_period <= 0 or d_period <= 0 or slowing <= 0:
        raise ValueError("DDIX_STOCHASTIC_PERIODS_MUST_BE_POSITIVE")
    h, l, c = _validate_ohlc(highs, lows, closes)
    if len(c) < k_period + slowing + d_period - 2:
        raise ValueError("DDIX_STOCHASTIC_INSUFFICIENT_HISTORY")

    numerators: list[float | None] = [None] * len(c)
    denominators: list[float | None] = [None] * len(c)
    for i in range(k_period - 1, len(c)):
        lowest = min(l[i - k_period + 1 : i + 1])
        highest = max(h[i - k_period + 1 : i + 1])
        denominator = highest - lowest
        if denominator <= 0.0:
            raise ValueError("DDIX_STOCHASTIC_ZERO_RANGE")
        numerators[i] = c[i] - lowest
        denominators[i] = denominator

    slowed_k: list[float | None] = [None] * len(c)
    first_slow = (k_period - 1) + (slowing - 1)
    for i in range(first_slow, len(c)):
        start = i - slowing + 1
        nums = numerators[start : i + 1]
        dens = denominators[start : i + 1]
        if any(v is None for v in nums) or any(v is None for v in dens):
            continue
        denominator_sum = sum(float(v) for v in dens if v is not None)
        if denominator_sum <= 0.0:
            raise ValueError("DDIX_STOCHASTIC_ZERO_SLOWED_RANGE")
        slowed_k[i] = 100.0 * (
            sum(float(v) for v in nums if v is not None) / denominator_sum
        )

    points: list[StochasticPoint] = []
    first_d = first_slow + (d_period - 1)
    for i in range(first_slow, len(c)):
        k_value = slowed_k[i]
        if k_value is None:
            continue
        d_value = None
        if i >= first_d:
            d_window = slowed_k[i - d_period + 1 : i + 1]
            if all(v is not None for v in d_window):
                d_value = sum(float(v) for v in d_window if v is not None) / float(d_period)
        points.append(
            StochasticPoint(
                index=i,
                k=float(k_value),
                d=d_value,
                zone=_zone(float(k_value)),
                provenance="METAQUOTES_LOW_HIGH_SUM_RATIO_SLOW_K_SMA_D",
            )
        )
    return tuple(points)


def classify_stochastic_cross(
    previous: StochasticPoint, current: StochasticPoint
) -> StochasticCrossEvidence:
    if previous.d is None or current.d is None:
        raise ValueError("DDIX_STOCHASTIC_SIGNAL_LINE_UNAVAILABLE")
    bullish = previous.k <= previous.d and current.k > current.d
    bearish = previous.k >= previous.d and current.k < current.d
    if current.k > current.d:
        bias = "BUY"
    elif current.k < current.d:
        bias = "SELL"
    else:
        bias = "NEUTRAL"

    reasons: list[str] = []
    if bullish:
        reasons.append("K_CROSSED_ABOVE_D")
    elif bearish:
        reasons.append("K_CROSSED_BELOW_D")
    else:
        reasons.append("NO_NEW_LINE_CROSS")
    if current.zone in {"OVERBOUGHT", "OVERSOLD"}:
        reasons.append("EXTREME_ZONE_CONTEXT_ONLY_NOT_REVERSAL_TRIGGER")

    return StochasticCrossEvidence(
        previous=previous,
        current=current,
        bullish_cross=bullish,
        bearish_cross=bearish,
        line_bias=bias,
        extreme_is_not_reversal_signal=True,
        reason_codes=tuple(reasons),
        provenance="DIDI_LINE_CROSS_SEMANTIC_WITH_EXTREMES_AS_CONTEXT",
    )
