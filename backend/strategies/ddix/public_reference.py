from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence


class NeedleDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NONE = "NONE"


@dataclass(frozen=True)
class MovingAverages3820:
    fast_3: float
    reference_8: float
    slow_20: float


@dataclass(frozen=True)
class ClassicNeedleEvidence:
    direction: NeedleDirection
    averages: MovingAverages3820
    body_low: float
    body_high: float
    all_averages_inside_body: bool
    directional_order_valid: bool


def _finite_number(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_VALUE_NOT_FINITE")
    return number


def simple_moving_average(values: Sequence[float], period: int) -> float:
    if period <= 0:
        raise ValueError("DDIX_PERIOD_MUST_BE_POSITIVE")
    if len(values) < period:
        raise ValueError("DDIX_INSUFFICIENT_HISTORY")
    window = [_finite_number(value) for value in values[-period:]]
    return sum(window) / float(period)


def compute_moving_averages_3_8_20(
    closes: Sequence[float],
) -> MovingAverages3820:
    return MovingAverages3820(
        fast_3=simple_moving_average(closes, 3),
        reference_8=simple_moving_average(closes, 8),
        slow_20=simple_moving_average(closes, 20),
    )


def classify_classic_needle_snapshot(
    candle_open: float,
    candle_close: float,
    averages: MovingAverages3820,
    tolerance: float = 0.0,
) -> ClassicNeedleEvidence:
    """Classify only the source-supported same-body 3/8/20 snapshot.

    This deliberately does not infer alert/confirmation sequencing, false points,
    DMI/ADX, Bollinger, TRIX, Stochastic, entry timing, stop or targets.
    """
    open_value = _finite_number(candle_open)
    close_value = _finite_number(candle_close)
    tolerance_value = _finite_number(tolerance)
    if tolerance_value < 0.0:
        raise ValueError("DDIX_TOLERANCE_MUST_BE_NONNEGATIVE")

    body_low = min(open_value, close_value)
    body_high = max(open_value, close_value)
    values = (averages.fast_3, averages.reference_8, averages.slow_20)
    finite_values = tuple(_finite_number(value) for value in values)
    inside = all(
        body_low - tolerance_value <= value <= body_high + tolerance_value
        for value in finite_values
    )

    bullish = averages.fast_3 > averages.reference_8 > averages.slow_20
    bearish = averages.slow_20 > averages.reference_8 > averages.fast_3
    direction = NeedleDirection.NONE
    if inside and bullish:
        direction = NeedleDirection.BULLISH
    elif inside and bearish:
        direction = NeedleDirection.BEARISH

    return ClassicNeedleEvidence(
        direction=direction,
        averages=averages,
        body_low=body_low,
        body_high=body_high,
        all_averages_inside_body=inside,
        directional_order_valid=bool(bullish or bearish),
    )
