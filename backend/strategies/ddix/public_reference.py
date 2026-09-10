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


class DidiIndexMethod(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RATIO = "RATIO"


@dataclass(frozen=True)
class DidiIndexLines:
    fast_line: float
    slow_line: float
    reference_axis: float
    method: DidiIndexMethod
    provenance: str


class FalsePointKind(str, Enum):
    FALSE_BUY = "FALSE_BUY"
    FALSE_SELL = "FALSE_SELL"
    NONE = "NONE"


@dataclass(frozen=True)
class FalsePointEvidence:
    kind: FalsePointKind
    previous: MovingAverages3820
    current: MovingAverages3820
    fast_cross_up: bool
    fast_cross_down: bool
    slow_displacement_previous: float
    slow_displacement_current: float
    slow_moving_away: bool
    continuation_bias: NeedleDirection
    provenance: str


def compute_didi_index_lines(
    averages: MovingAverages3820,
    method: DidiIndexMethod = DidiIndexMethod.ABSOLUTE,
) -> DidiIndexLines:
    fast = _finite_number(averages.fast_3)
    reference = _finite_number(averages.reference_8)
    slow = _finite_number(averages.slow_20)
    if method is DidiIndexMethod.ABSOLUTE:
        fast_line = fast - reference
        slow_line = slow - reference
        provenance = "REFERENCE_CANDIDATE_COMMUNITY_ABSOLUTE_DISTANCE"
    elif method is DidiIndexMethod.RATIO:
        if reference == 0.0:
            raise ValueError("DDIX_REFERENCE_AVERAGE_ZERO")
        fast_line = (fast / reference) - 1.0
        slow_line = (slow / reference) - 1.0
        provenance = "REFERENCE_CANDIDATE_RATIO_DISTANCE"
    else:
        raise ValueError("DDIX_INDEX_METHOD_UNSUPPORTED")
    return DidiIndexLines(
        fast_line=fast_line,
        slow_line=slow_line,
        reference_axis=0.0,
        method=method,
        provenance=provenance,
    )


def classify_false_point_candidate(
    previous: MovingAverages3820,
    current: MovingAverages3820,
) -> FalsePointEvidence:
    """Secondary-source candidate for Didi's Ponto Falso.

    FALSE_BUY: fast crosses above MA8 while MA20 is already above MA8 and
    moving farther upward. This contradicts the apparent buy and implies a
    bearish-continuation bias.

    FALSE_SELL is the exact symmetric case below MA8.
    """
    for value in (
        previous.fast_3, previous.reference_8, previous.slow_20,
        current.fast_3, current.reference_8, current.slow_20,
    ):
        _finite_number(value)

    prev_fast = previous.fast_3 - previous.reference_8
    curr_fast = current.fast_3 - current.reference_8
    prev_slow = previous.slow_20 - previous.reference_8
    curr_slow = current.slow_20 - current.reference_8

    cross_up = prev_fast <= 0.0 and curr_fast > 0.0
    cross_down = prev_fast >= 0.0 and curr_fast < 0.0
    false_buy = cross_up and prev_slow > 0.0 and curr_slow > prev_slow
    false_sell = cross_down and prev_slow < 0.0 and curr_slow < prev_slow

    kind = FalsePointKind.NONE
    bias = NeedleDirection.NONE
    moving_away = False
    if false_buy:
        kind = FalsePointKind.FALSE_BUY
        bias = NeedleDirection.BEARISH
        moving_away = True
    elif false_sell:
        kind = FalsePointKind.FALSE_SELL
        bias = NeedleDirection.BULLISH
        moving_away = True

    return FalsePointEvidence(
        kind=kind,
        previous=previous,
        current=current,
        fast_cross_up=cross_up,
        fast_cross_down=cross_down,
        slow_displacement_previous=prev_slow,
        slow_displacement_current=curr_slow,
        slow_moving_away=moving_away,
        continuation_bias=bias,
        provenance="REFERENCE_CANDIDATE_CST_PLUS_COMMUNITY_FORMALIZATION",
    )


class IndexedAlignment(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    UNALIGNED = "UNALIGNED"


@dataclass(frozen=True)
class IndexedAlignmentEvidence:
    alignment: IndexedAlignment
    fast_line: float
    slow_line: float
    reference_axis: float
    source_contract: str


def classify_indexed_alignment(lines: DidiIndexLines) -> IndexedAlignmentEvidence:
    """Classify sign/order only; this is not sufficient to call an Agulhada."""
    fast = _finite_number(lines.fast_line)
    slow = _finite_number(lines.slow_line)
    axis = _finite_number(lines.reference_axis)
    alignment = IndexedAlignment.UNALIGNED
    if fast > axis and slow < axis:
        alignment = IndexedAlignment.BULLISH
    elif fast < axis and slow > axis:
        alignment = IndexedAlignment.BEARISH
    return IndexedAlignmentEvidence(
        alignment=alignment,
        fast_line=fast,
        slow_line=slow,
        reference_axis=axis,
        source_contract="NEL_DIDI_INDEX_SIGN_ORDER_ONLY",
    )
