from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, Tuple


DDIX_BOLLINGER_PERIOD_CANDIDATE = 8
DDIX_BOLLINGER_DEVIATION_CANDIDATE = 2.0


@dataclass(frozen=True)
class BollingerSnapshot:
    basis: float
    stddev: float
    upper: float
    lower: float
    width: float
    width_pct: float | None
    period: int
    deviation: float
    provenance: str


@dataclass(frozen=True)
class BollingerOpeningEvidence:
    previous: BollingerSnapshot
    current: BollingerSnapshot
    width_increasing: bool
    width_decreasing: bool
    upper_rising: bool
    lower_falling: bool
    mouth_opening_candidate: bool
    mouth_closing_candidate: bool
    reason_codes: Tuple[str, ...]
    provenance: str


def _finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("DDIX_BOLLINGER_VALUE_NOT_FINITE")
    return number


def population_stddev(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("DDIX_BOLLINGER_EMPTY_WINDOW")
    clean = tuple(_finite(value) for value in values)
    mean = sum(clean) / float(len(clean))
    variance = sum((value - mean) ** 2 for value in clean) / float(len(clean))
    return math.sqrt(variance)


def compute_bollinger_snapshot(
    closes: Sequence[float],
    period: int = DDIX_BOLLINGER_PERIOD_CANDIDATE,
    deviation: float = DDIX_BOLLINGER_DEVIATION_CANDIDATE,
) -> BollingerSnapshot:
    if period <= 0:
        raise ValueError("DDIX_BOLLINGER_PERIOD_MUST_BE_POSITIVE")
    if len(closes) < period:
        raise ValueError("DDIX_BOLLINGER_INSUFFICIENT_HISTORY")
    dev = _finite(deviation)
    if dev <= 0.0:
        raise ValueError("DDIX_BOLLINGER_DEVIATION_MUST_BE_POSITIVE")

    window = tuple(_finite(value) for value in closes[-period:])
    basis = sum(window) / float(period)
    stddev = population_stddev(window)
    upper = basis + (stddev * dev)
    lower = basis - (stddev * dev)
    width = upper - lower
    width_pct = None if basis == 0.0 else (width / basis) * 100.0

    return BollingerSnapshot(
        basis=basis,
        stddev=stddev,
        upper=upper,
        lower=lower,
        width=width,
        width_pct=width_pct,
        period=period,
        deviation=dev,
        provenance="METAQUOTES_N_POP_STDDEV_PLUS_NELOGICA_BANDWIDTH",
    )


def classify_bollinger_opening_candidate(
    previous: BollingerSnapshot,
    current: BollingerSnapshot,
) -> BollingerOpeningEvidence:
    width_increasing = current.width > previous.width
    width_decreasing = current.width < previous.width
    upper_rising = current.upper > previous.upper
    lower_falling = current.lower < previous.lower
    mouth_opening = width_increasing and upper_rising and lower_falling
    mouth_closing = width_decreasing

    reasons = []
    if mouth_opening:
        reasons.append("WIDTH_EXPANDING_UPPER_UP_LOWER_DOWN")
    elif mouth_closing:
        reasons.append("WIDTH_CONTRACTING")
    else:
        if width_increasing:
            reasons.append("WIDTH_EXPANDING_WITHOUT_TWO_SIDED_OPENING")
        else:
            reasons.append("NO_OBJECTIVE_BOLLINGER_OPENING")

    return BollingerOpeningEvidence(
        previous=previous,
        current=current,
        width_increasing=width_increasing,
        width_decreasing=width_decreasing,
        upper_rising=upper_rising,
        lower_falling=lower_falling,
        mouth_opening_candidate=mouth_opening,
        mouth_closing_candidate=mouth_closing,
        reason_codes=tuple(reasons),
        provenance="DIDI_BOLLINGER_SEMANTIC_PLUS_OBJECTIVE_WIDTH_CANDIDATE",
    )
