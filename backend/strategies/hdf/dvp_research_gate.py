from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .prospective_fibonacci import ConfirmedPivot, ProspectiveFibResult, audit_latest_completed_leg


@dataclass(frozen=True)
class DVPResearchGateResult:
    eligible: bool
    status: str
    fibonacci: ProspectiveFibResult | None
    reason: str


def evaluate_dvp_research_gate(*, direction: str, divergence_pass: bool, volume_pass: bool,
                               pattern_pass: bool, pivots: Sequence[ConfirmedPivot],
                               decision_index: int, candle_low: float, candle_high: float,
                               fib_policy_promoted: bool = False) -> DVPResearchGateResult:
    """Research-only four-confluence gate; never promotes unresolved Fibonacci policy."""
    if not divergence_pass:
        return DVPResearchGateResult(False, "FAIL", None, "DIVERGENCE_FAIL")
    if not volume_pass:
        return DVPResearchGateResult(False, "FAIL", None, "VOLUME_FAIL")
    if not pattern_pass:
        return DVPResearchGateResult(False, "FAIL", None, "PATTERN_FAIL")
    fib = audit_latest_completed_leg(
        direction=direction, pivots=pivots, decision_index=decision_index,
        candle_low=candle_low, candle_high=candle_high,
    )
    if fib.status != "PASS":
        return DVPResearchGateResult(False, fib.status, fib, f"FIBONACCI_{fib.status}")
    if not fib_policy_promoted:
        return DVPResearchGateResult(False, "RESEARCH_ONLY", fib, "FIBONACCI_POLICY_NOT_PROMOTED")
    return DVPResearchGateResult(True, "PASS", fib, "FOUR_CONFLUENCES_CONFIRMED")
