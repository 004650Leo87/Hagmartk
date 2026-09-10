from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Tuple


class DmiDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    FLAT = "FLAT"


class DidiTrendState(str, Enum):
    TREND_PRESENT = "TREND_PRESENT"
    NO_TREND = "NO_TREND"


@dataclass(frozen=True)
class DmiSnapshot:
    di_plus: float
    di_minus: float
    adx: float


@dataclass(frozen=True)
class DmiContextEvidence:
    previous: DmiSnapshot
    current: DmiSnapshot
    direction: DmiDirection
    trend_state: DidiTrendState
    trend_present: bool
    adx_rising: bool
    adx_falling: bool
    no_trend_adx_below_both: bool
    no_trend_adx_falling_le_level: bool
    reason_codes: Tuple[str, ...]
    provenance: str


@dataclass(frozen=True)
class AdxKickEvidence:
    detected: bool
    prior_adx: float
    peak_adx: float
    current_adx: float
    provenance: str


def _validated_snapshot(snapshot: DmiSnapshot) -> DmiSnapshot:
    values = (snapshot.di_plus, snapshot.di_minus, snapshot.adx)
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("DDIX_DMI_VALUE_NOT_FINITE")
    if any(float(value) < 0.0 or float(value) > 100.0 for value in values):
        raise ValueError("DDIX_DMI_VALUE_OUT_OF_RANGE")
    return DmiSnapshot(*(float(value) for value in values))


def classify_didi_dmi_context(
    previous: DmiSnapshot,
    current: DmiSnapshot,
    no_trend_level: float = 32.0,
) -> DmiContextEvidence:
    prev = _validated_snapshot(previous)
    curr = _validated_snapshot(current)
    level = float(no_trend_level)
    if not math.isfinite(level) or level < 0.0 or level > 100.0:
        raise ValueError("DDIX_DMI_LEVEL_INVALID")

    direction = DmiDirection.FLAT
    if curr.di_plus > curr.di_minus:
        direction = DmiDirection.BULLISH
    elif curr.di_minus > curr.di_plus:
        direction = DmiDirection.BEARISH

    adx_rising = curr.adx > prev.adx
    adx_falling = curr.adx < prev.adx
    below_both = curr.adx < curr.di_plus and curr.adx < curr.di_minus
    falling_le_level = adx_falling and curr.adx <= level
    no_trend = below_both or falling_le_level

    reasons = []
    if below_both:
        reasons.append("ADX_BELOW_BOTH_DI")
    if falling_le_level:
        reasons.append("ADX_FALLING_LE_32")
    if not reasons:
        reasons.append("TREND_PRESENT_BY_DIDI_RULE")

    return DmiContextEvidence(
        previous=prev,
        current=curr,
        direction=direction,
        trend_state=DidiTrendState.NO_TREND if no_trend else DidiTrendState.TREND_PRESENT,
        trend_present=not no_trend,
        adx_rising=adx_rising,
        adx_falling=adx_falling,
        no_trend_adx_below_both=below_both,
        no_trend_adx_falling_le_level=falling_le_level,
        reason_codes=tuple(reasons),
        provenance="DIDI_CST_CLEAR_SEMANTIC_REFERENCE",
    )


def classify_adx_kick_candidate(
    prior_adx: float,
    peak_adx: float,
    current_adx: float,
) -> AdxKickEvidence:
    values = tuple(float(value) for value in (prior_adx, peak_adx, current_adx))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("DDIX_ADX_VALUE_NOT_FINITE")
    if any(value < 0.0 or value > 100.0 for value in values):
        raise ValueError("DDIX_ADX_VALUE_OUT_OF_RANGE")
    detected = values[1] > values[0] and values[2] < values[1]
    return AdxKickEvidence(
        detected=detected,
        prior_adx=values[0],
        peak_adx=values[1],
        current_adx=values[2],
        provenance="DIDI_CST_ADX_KICK_SEMANTIC_REFERENCE",
    )
