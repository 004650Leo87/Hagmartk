from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .fibonacci_audit import SOURCE_LEVELS, mirrored_extension_levels


@dataclass(frozen=True)
class ConfirmedPivot:
    index: int
    price: float
    is_high: bool
    confirmed_at_index: int
    time: str = ""


@dataclass(frozen=True)
class ProspectiveFibResult:
    status: str
    direction: str
    anchor_a: ConfirmedPivot | None
    anchor_b: ConfirmedPivot | None
    matched_levels: tuple[float, ...]
    matched_prices: tuple[float, ...]
    reason: str


def select_latest_completed_leg(*, direction: str, pivots: Sequence[ConfirmedPivot], decision_index: int):
    """Select the latest opposite->same-direction leg known at decision time.

    This is a research policy, not yet the frozen HAGMARTK DVP contract.
    """
    d = direction.upper()
    if d not in {"BULLISH", "BEARISH"}:
        raise ValueError("direction must be BULLISH or BEARISH")
    known = sorted((p for p in pivots if p.confirmed_at_index <= decision_index), key=lambda p: p.index)
    endpoint_is_high = d == "BULLISH"
    endpoints = [p for p in known if p.is_high == endpoint_is_high]
    for b in reversed(endpoints):
        starts = [p for p in known if p.index < b.index and p.is_high != endpoint_is_high]
        if starts:
            a = starts[-1]
            if (d == "BULLISH" and b.price > a.price) or (d == "BEARISH" and b.price < a.price):
                return a, b
    return None, None


def audit_latest_completed_leg(*, direction: str, pivots: Sequence[ConfirmedPivot], decision_index: int,
                               candle_low: float, candle_high: float) -> ProspectiveFibResult:
    """Evaluate only the single leg selected without future data or retrospective fitting."""
    a, b = select_latest_completed_leg(direction=direction, pivots=pivots, decision_index=decision_index)
    if a is None or b is None:
        return ProspectiveFibResult("UNRESOLVED", direction.upper(), None, None, (), (), "NO_CONFIRMED_LEG")
    levels = mirrored_extension_levels(a.price, b.price)
    contacts = [(level, price) for level, price in levels.items() if candle_low <= price <= candle_high]
    return ProspectiveFibResult(
        "PASS" if contacts else "FAIL", direction.upper(), a, b,
        tuple(level for level, _ in contacts), tuple(price for _, price in contacts),
        "LEVEL_INSIDE_DECISION_CANDLE" if contacts else "NO_LEVEL_INSIDE_DECISION_CANDLE",
    )


def select_strict_pre_reversal_leg(*, direction: str, pivots: Sequence[ConfirmedPivot], decision_index: int, reversal_pivot_index: int):
    """Latest valid completed leg known by decision time and structurally before P2/reversal."""
    d = direction.upper()
    if d not in {"BULLISH", "BEARISH"}:
        raise ValueError("direction must be BULLISH or BEARISH")
    known = sorted((p for p in pivots if p.confirmed_at_index <= decision_index and p.index < reversal_pivot_index), key=lambda p: p.index)
    endpoint_is_high = d == "BULLISH"
    for b in reversed([p for p in known if p.is_high == endpoint_is_high]):
        starts = [p for p in known if p.index < b.index and p.is_high != endpoint_is_high]
        if starts:
            a = starts[-1]
            if (d == "BULLISH" and b.price > a.price) or (d == "BEARISH" and b.price < a.price):
                return a, b
    return None, None

def audit_strict_pre_reversal_leg(*, direction: str, pivots: Sequence[ConfirmedPivot], decision_index: int, reversal_pivot_index: int, candle_low: float, candle_high: float) -> ProspectiveFibResult:
    a, b = select_strict_pre_reversal_leg(direction=direction, pivots=pivots, decision_index=decision_index, reversal_pivot_index=reversal_pivot_index)
    if a is None or b is None:
        return ProspectiveFibResult("UNRESOLVED", direction.upper(), None, None, (), (), "NO_STRICT_PRE_REVERSAL_LEG")
    levels = mirrored_extension_levels(a.price, b.price)
    contacts = [(level, price) for level, price in levels.items() if candle_low <= price <= candle_high]
    return ProspectiveFibResult("PASS" if contacts else "FAIL", direction.upper(), a, b, tuple(x[0] for x in contacts), tuple(x[1] for x in contacts), "LEVEL_INSIDE_DECISION_CANDLE" if contacts else "NO_LEVEL_INSIDE_DECISION_CANDLE")
