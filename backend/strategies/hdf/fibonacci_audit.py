from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable


SOURCE_LEVELS = (0.618, 1.0, 1.618, 2.0, 2.618)


class FibonacciAuditStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ANCHOR_UNRESOLVED = "ANCHOR_UNRESOLVED"


@dataclass(frozen=True)
class FibonacciExtensionEvidence:
    direction: str
    anchor_a: float
    anchor_b: float
    anchor_c: float
    observed_price: float
    tolerance: float
    levels: Dict[float, float]
    matched_level: float | None
    matched_price: float | None
    status: FibonacciAuditStatus


def mirrored_extension_levels(anchor_a: float, anchor_b: float, *, levels: Iterable[float] = SOURCE_LEVELS) -> Dict[float, float]:
    """Trend-based extension using C=B (the source-described min/max + repeated endpoint construction)."""
    a = float(anchor_a)
    b = float(anchor_b)
    leg = b - a
    if leg == 0.0:
        raise ValueError("Fibonacci extension requires distinct anchors")
    return {float(level): b + leg * float(level) for level in levels}


def audit_explicit_extension(*, direction: str, anchor_a: float, anchor_b: float, observed_price: float, tolerance: float) -> FibonacciExtensionEvidence:
    """Audit one explicit, externally selected anchor pair. This function never chooses pivots."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    direction_norm = direction.upper()
    if direction_norm not in {"BULLISH", "BEARISH"}:
        raise ValueError("direction must be BULLISH or BEARISH")
    if direction_norm == "BULLISH" and not anchor_b > anchor_a:
        raise ValueError("bullish extension requires anchor_b > anchor_a")
    if direction_norm == "BEARISH" and not anchor_b < anchor_a:
        raise ValueError("bearish extension requires anchor_b < anchor_a")

    projected = mirrored_extension_levels(anchor_a, anchor_b)
    obs = float(observed_price)
    match = min(projected.items(), key=lambda item: abs(obs - item[1]))
    level, price = match
    passed = abs(obs - price) <= float(tolerance)
    return FibonacciExtensionEvidence(
        direction=direction_norm, anchor_a=float(anchor_a), anchor_b=float(anchor_b), anchor_c=float(anchor_b),
        observed_price=obs, tolerance=float(tolerance), levels=projected,
        matched_level=level if passed else None, matched_price=price if passed else None,
        status=FibonacciAuditStatus.PASS if passed else FibonacciAuditStatus.FAIL,
    )
