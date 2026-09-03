from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .fibonacci_audit import SOURCE_LEVELS, mirrored_extension_levels
from .prospective_fibonacci import ConfirmedPivot


class FibonacciConstructionMode(str, Enum):
    PRE_REVERSAL = "PRE_REVERSAL"
    POST_REVERSAL = "POST_REVERSAL"
    HIGHER_TIMEFRAME_CONTEXT = "HIGHER_TIMEFRAME_CONTEXT"


@dataclass(frozen=True)
class FibonacciConstructionEvidence:
    mode: FibonacciConstructionMode
    source_timeframe: str
    decision_timeframe: str
    anchor_a: ConfirmedPivot
    anchor_b: ConfirmedPivot
    levels: dict[float, float]


def construct_extension(*, mode: FibonacciConstructionMode, source_timeframe: str,
                        decision_timeframe: str, anchor_a: ConfirmedPivot,
                        anchor_b: ConfirmedPivot) -> FibonacciConstructionEvidence:
    """Build a source-described Fibonacci mode from explicit, already-selected anchors.

    Anchor selection remains a separate research policy. This function never chooses swings.
    """
    if anchor_a.confirmed_at_index > anchor_b.confirmed_at_index:
        raise ValueError("anchor A must be known no later than anchor B")
    if anchor_a.price == anchor_b.price:
        raise ValueError("Fibonacci anchors must have distinct prices")
    if mode is not FibonacciConstructionMode.HIGHER_TIMEFRAME_CONTEXT and source_timeframe != decision_timeframe:
        raise ValueError("same-timeframe Fibonacci mode requires matching timeframes")
    if mode is FibonacciConstructionMode.HIGHER_TIMEFRAME_CONTEXT and source_timeframe == decision_timeframe:
        raise ValueError("higher-timeframe context requires distinct timeframes")

    return FibonacciConstructionEvidence(
        mode=mode,
        source_timeframe=source_timeframe,
        decision_timeframe=decision_timeframe,
        anchor_a=anchor_a,
        anchor_b=anchor_b,
        levels=mirrored_extension_levels(anchor_a.price, anchor_b.price, levels=SOURCE_LEVELS),
    )
