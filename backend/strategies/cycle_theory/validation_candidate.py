"""Frozen Cycle Theory V111 baseline snapshot for validation research."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .inputs import baseline_inputs


CYCLE_THEORY_V111_SOURCE_SHA256 = (
    "32814ecf0a1ca6577f93d99e1bab358f92eed875314bc5c180ca77bc769096a2"
)


def _canonical(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def baseline_parameter_payload() -> dict[str, Any]:
    return _canonical(asdict(baseline_inputs()))


@dataclass(frozen=True)
class CycleTheoryValidationCandidate:
    candidate_id: str = "cycle_theory_v111_baseline"
    candidate_version: str = "1.0.0"
    strategy_id: str = "cycle_theory_v111_fidelity"
    source_version: str = "111.00"
    source_sha256: str = CYCLE_THEORY_V111_SOURCE_SHA256
    research_status: str = "BASELINE_SCREENING"

    def parameter_payload(self) -> dict[str, Any]:
        return baseline_parameter_payload()

    def parameter_hash(self) -> str:
        payload = {
            "candidate_id": self.candidate_id,
            "candidate_version": self.candidate_version,
            "strategy_id": self.strategy_id,
            "source_version": self.source_version,
            "source_sha256": self.source_sha256,
            "parameters": self.parameter_payload(),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_immutability(self, expected_hash: str) -> bool:
        return self.parameter_hash() == expected_hash


CYCLE_THEORY_V111_BASELINE = CycleTheoryValidationCandidate()
CYCLE_THEORY_V111_BASELINE_HASH = CYCLE_THEORY_V111_BASELINE.parameter_hash()
