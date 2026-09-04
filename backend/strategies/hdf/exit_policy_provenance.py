from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, Tuple


class ExitPolicyProvenance(str, Enum):
    HAGMARTK_QUANT_BENCHMARK = "HAGMARTK_QUANT_BENCHMARK"
    SOURCE_DESCRIBED_DISCRETIONARY = "SOURCE_DESCRIBED_DISCRETIONARY"


@dataclass(frozen=True)
class ExitPolicyProvenanceContract:
    policy_id: str
    provenance: ExitPolicyProvenance
    source_described: bool
    deterministic_automation: bool
    promotion_allowed: bool
    original_divap_claim_allowed: bool
    target_levels: Tuple[float, ...]
    allocation_policy: str
    stop_management_policy: str
    notes: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        payload["target_levels"] = list(self.target_levels)
        payload["notes"] = list(self.notes)
        return payload


EXIT_2R_BENCHMARK = ExitPolicyProvenanceContract(
    policy_id="EXIT_2R",
    provenance=ExitPolicyProvenance.HAGMARTK_QUANT_BENCHMARK,
    source_described=False,
    deterministic_automation=True,
    promotion_allowed=False,
    original_divap_claim_allowed=False,
    target_levels=(2.0,),
    allocation_policy="CLOSE_100_PERCENT_AT_2R",
    stop_management_policy="INITIAL_STRUCTURAL_STOP_UNTIL_TERMINAL",
    notes=(
        "Quantitative HAGMARTK benchmark retained by the frozen candidate V1.",
        "Numerical coincidence with Fibonacci 200% is conditional and does not change provenance.",
    ),
)

DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE = ExitPolicyProvenanceContract(
    policy_id="DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE",
    provenance=ExitPolicyProvenance.SOURCE_DESCRIBED_DISCRETIONARY,
    source_described=True,
    deterministic_automation=False,
    promotion_allowed=False,
    original_divap_claim_allowed=False,
    target_levels=(0.618, 1.0, 1.618, 2.0, 2.618),
    allocation_policy="UNRESOLVED / TRADER_DISCRETION",
    stop_management_policy="UNRESOLVED / NO UNIVERSAL SOURCE RULE",
    notes=(
        "Public source describes partial realization along Fibonacci targets.",
        "Public source explicitly allows different management choices by trader profile.",
        "No universal percentage allocation or mandatory stop-move rule is frozen.",
    ),
)


EXIT_POLICY_PROVENANCE_REGISTRY = {
    EXIT_2R_BENCHMARK.policy_id: EXIT_2R_BENCHMARK,
    DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE.policy_id: DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE,
}


def get_exit_policy_provenance(policy_id: str) -> ExitPolicyProvenanceContract:
    try:
        return EXIT_POLICY_PROVENANCE_REGISTRY[policy_id]
    except KeyError as exc:
        raise KeyError(f"Unknown exit policy provenance contract: {policy_id}") from exc
