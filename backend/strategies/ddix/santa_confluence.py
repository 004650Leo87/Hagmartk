from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from backend.strategies.ddix.bollinger_reference import BollingerOpeningEvidence
from backend.strategies.ddix.dmi_reference import DmiContextEvidence, DmiDirection
from backend.strategies.ddix.public_reference import ClassicNeedleEvidence, NeedleDirection
from backend.strategies.ddix.stochastic_reference import StochasticCrossEvidence
from backend.strategies.ddix.trix_reference import TrixCrossEvidence


class SantaConfluenceLevel(str, Enum):
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NEEDLE_ONLY = "NEEDLE_ONLY"
    PRIMARY_CONTEXT_ALIGNED = "PRIMARY_CONTEXT_ALIGNED"
    SANTA_CONFLUENCE_CANDIDATE = "SANTA_CONFLUENCE_CANDIDATE"


@dataclass(frozen=True)
class SantaConfluenceEvidence:
    direction: NeedleDirection
    level: SantaConfluenceLevel
    classic_needle: bool
    dmi_direction_aligned: bool
    dmi_trend_present: bool
    adx_accelerating: bool
    bollinger_opening: bool
    trix_aligned: bool
    stochastic_aligned: bool
    semantic_santa_candidate: bool
    operationally_approved: bool
    reason_codes: Tuple[str, ...]
    unresolved_dependencies: Tuple[str, ...]
    provenance: str


DDIX_SANTA_UNRESOLVED_DEPENDENCIES = (
    "DDIX_NUMERIC_PLATFORM_PARITY_OPEN",
    "DMI_ADX_PLATFORM_BUFFER_PARITY_OPEN",
    "BOLLINGER_PLATFORM_BUFFER_PARITY_OPEN",
    "TRIX_SIGNAL_MODE_AND_PLATFORM_PARITY_OPEN",
    "STOCHASTIC_PLATFORM_BUFFER_PARITY_OPEN",
)


def _expected_bias(direction: NeedleDirection) -> str:
    if direction is NeedleDirection.BULLISH:
        return "BUY"
    if direction is NeedleDirection.BEARISH:
        return "SELL"
    return "NONE"


def _trix_bias(evidence: TrixCrossEvidence) -> str:
    if evidence.current_trix > evidence.current_signal:
        return "BUY"
    if evidence.current_trix < evidence.current_signal:
        return "SELL"
    return "NEUTRAL"


def _dmi_matches(direction: NeedleDirection, evidence: DmiContextEvidence) -> bool:
    if direction is NeedleDirection.BULLISH:
        return evidence.direction is DmiDirection.BULLISH
    if direction is NeedleDirection.BEARISH:
        return evidence.direction is DmiDirection.BEARISH
    return False


def classify_santa_confluence_candidate(
    needle: ClassicNeedleEvidence,
    dmi: DmiContextEvidence,
    bollinger: BollingerOpeningEvidence,
    trix: TrixCrossEvidence,
    stochastic: StochasticCrossEvidence,
) -> SantaConfluenceEvidence:
    direction = needle.direction
    classic_needle = direction is not NeedleDirection.NONE
    expected_bias = _expected_bias(direction)
    dmi_aligned = _dmi_matches(direction, dmi)
    trend_present = bool(dmi.trend_present)
    adx_accelerating = bool(dmi.adx_rising)
    bollinger_opening = bool(bollinger.mouth_opening_candidate)
    trix_aligned = classic_needle and _trix_bias(trix) == expected_bias
    stochastic_aligned = classic_needle and stochastic.line_bias == expected_bias

    primary_context = (
        classic_needle
        and dmi_aligned
        and trend_present
        and bollinger_opening
    )
    santa = (
        primary_context
        and adx_accelerating
        and trix_aligned
        and stochastic_aligned
    )

    if santa:
        level = SantaConfluenceLevel.SANTA_CONFLUENCE_CANDIDATE
    elif primary_context:
        level = SantaConfluenceLevel.PRIMARY_CONTEXT_ALIGNED
    elif classic_needle:
        level = SantaConfluenceLevel.NEEDLE_ONLY
    else:
        level = SantaConfluenceLevel.NOT_QUALIFIED

    reasons: list[str] = []
    if not classic_needle:
        reasons.append("CLASSIC_NEEDLE_MISSING")
    if classic_needle and not dmi_aligned:
        reasons.append("DMI_DIRECTION_NOT_ALIGNED")
    if classic_needle and not trend_present:
        reasons.append("DMI_TREND_NOT_PRESENT")
    if classic_needle and not bollinger_opening:
        reasons.append("BOLLINGER_NOT_OPENING")
    if primary_context and not adx_accelerating:
        reasons.append("ADX_NOT_ACCELERATING")
    if primary_context and not trix_aligned:
        reasons.append("TRIX_NOT_ALIGNED")
    if primary_context and not stochastic_aligned:
        reasons.append("STOCHASTIC_NOT_ALIGNED")
    if santa:
        reasons.append("SEMANTIC_SANTA_CONFLUENCE_CANDIDATE")
    reasons.append("OPERATIONAL_PROMOTION_BLOCKED_BY_OPEN_PARITY_GATES")

    return SantaConfluenceEvidence(
        direction=direction,
        level=level,
        classic_needle=classic_needle,
        dmi_direction_aligned=dmi_aligned,
        dmi_trend_present=trend_present,
        adx_accelerating=adx_accelerating,
        bollinger_opening=bollinger_opening,
        trix_aligned=trix_aligned,
        stochastic_aligned=stochastic_aligned,
        semantic_santa_candidate=santa,
        operationally_approved=False,
        reason_codes=tuple(reasons),
        unresolved_dependencies=DDIX_SANTA_UNRESOLVED_DEPENDENCIES,
        provenance="PRIMARY_DIDI_CONTEXT_PLUS_SECONDARY_SANTA_LABEL_CANDIDATE",
    )
