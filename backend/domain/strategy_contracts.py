from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH, HDF_ROBUST_CANDIDATE_V1
from backend.domain.market_events import MarketEventClass
from backend.strategies.cycle_theory.validation_candidate import (
    CYCLE_THEORY_V111_BASELINE,
    CYCLE_THEORY_V111_BASELINE_HASH,
)


class ProductStrategyStage(str, Enum):
    RESEARCH = "RESEARCH"
    FIDELITY = "FIDELITY"
    VALIDATION = "VALIDATION"
    SHADOW = "SHADOW"
    EVENT_ELIGIBLE = "EVENT_ELIGIBLE"
    RETIRED = "RETIRED"


class PublicationCapability(str, Enum):
    NONE = "NONE"
    GATED = "GATED"
    ELIGIBLE = "ELIGIBLE"


@dataclass(frozen=True)
class StrategyContract:
    strategy_id: str
    version: str
    display_name: str
    family: str
    stage: ProductStrategyStage
    source_of_truth: str
    owner_module: str
    candidate_id: str = ""
    parameter_hash: str = ""
    publication_capability: PublicationCapability = PublicationCapability.NONE
    publication_gate_id: str = ""
    allowed_event_classes: Tuple[MarketEventClass, ...] = field(default_factory=tuple)
    evidence_keys: Tuple[str, ...] = field(default_factory=tuple)
    real_order_execution_allowed: bool = False
    limitations: Tuple[str, ...] = field(default_factory=tuple)

    def validation_errors(self) -> Tuple[str, ...]:
        errors = []
        for name, value in (
            ("strategy_id", self.strategy_id),
            ("version", self.version),
            ("display_name", self.display_name),
            ("family", self.family),
            ("source_of_truth", self.source_of_truth),
            ("owner_module", self.owner_module),
        ):
            if not str(value).strip():
                errors.append(f"MISSING_{name.upper()}")

        if self.stage == ProductStrategyStage.SHADOW:
            if not self.candidate_id.strip():
                errors.append("SHADOW_MISSING_CANDIDATE_ID")
            if not self.parameter_hash.strip():
                errors.append("SHADOW_MISSING_PARAMETER_HASH")

        if self.publication_capability == PublicationCapability.ELIGIBLE and not self.publication_gate_id.strip():
            errors.append("ELIGIBLE_WITHOUT_PUBLICATION_GATE")
        return tuple(errors)


class StrategyContractRegistry:
    def __init__(self) -> None:
        self._contracts: Dict[str, StrategyContract] = {}

    @staticmethod
    def _key(strategy_id: str, version: str) -> str:
        return f"{strategy_id}:{version}"

    def register(self, contract: StrategyContract) -> None:
        errors = contract.validation_errors()
        if errors:
            raise ValueError(f"Invalid strategy contract: {errors}")
        key = self._key(contract.strategy_id, contract.version)
        if key in self._contracts:
            raise ValueError(f"Duplicate strategy contract: {key}")
        self._contracts[key] = contract

    def get(self, strategy_id: str, version: Optional[str] = None) -> Optional[StrategyContract]:
        if version is not None:
            return self._contracts.get(self._key(strategy_id, version))
        matches = [c for c in self._contracts.values() if c.strategy_id == strategy_id]
        if not matches:
            return None
        if len(matches) > 1:
            raise ValueError(f"Version required for multi-version strategy: {strategy_id}")
        return matches[0]

    def list_all(self) -> Tuple[StrategyContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda c: (c.strategy_id, c.version)))


def build_product_strategy_registry() -> StrategyContractRegistry:
    registry = StrategyContractRegistry()

    hdf = StrategyContract(
        strategy_id=HDF_ROBUST_CANDIDATE_V1.strategy_id,
        version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
        display_name=HDF_ROBUST_CANDIDATE_V1.display_name,
        family="HDF",
        stage=ProductStrategyStage.SHADOW,
        source_of_truth="backend/domain/candidate.py::HDF_ROBUST_CANDIDATE_V1",
        owner_module="backend.strategies.hdf",
        candidate_id=HDF_ROBUST_CANDIDATE_V1.candidate_id,
        parameter_hash=HDF_CANDIDATE_V1_PARAMETER_HASH,
        publication_capability=PublicationCapability.GATED,
        publication_gate_id="HDF_SHADOW_EVIDENCE_GATE_V1",
        allowed_event_classes=(
            MarketEventClass.RADAR,
            MarketEventClass.RESEARCH_UPDATE,
            MarketEventClass.QUANT_EVENT,
        ),
        evidence_keys=("HDF_SHADOW_EVIDENCE_V1", "HDF_FIBONACCI_RESEARCH_V1"),
        real_order_execution_allowed=False,
        limitations=tuple(HDF_ROBUST_CANDIDATE_V1.limitations),
    )
    registry.register(hdf)

    cycle_v111 = StrategyContract(
        strategy_id="cycle_theory_v111_fidelity",
        version="111.00",
        display_name="Cycle Theory V111 — Validation Baseline",
        family="CYCLE_THEORY",
        stage=ProductStrategyStage.VALIDATION,
        source_of_truth="TEORIA_DOS_CICLOS_ULTIMATE_1.mq5 v111.00",
        owner_module="backend.strategies.cycle_theory",
        candidate_id=CYCLE_THEORY_V111_BASELINE.candidate_id,
        parameter_hash=CYCLE_THEORY_V111_BASELINE_HASH,
        publication_capability=PublicationCapability.NONE,
        publication_gate_id="",
        allowed_event_classes=(MarketEventClass.RESEARCH_UPDATE,),
        evidence_keys=("CYCLE_THEORY_V111_FIDELITY_EVIDENCE",),
        real_order_execution_allowed=False,
        limitations=(
            "Validation baseline; publication remains disabled.",
            "Observed Bid/Ask tick replay is available, but broker acceptance, slippage, commission and swap remain partial/modelled.",
            "No profitability or real-trading claim is authorized.",
        ),
    )
    registry.register(cycle_v111)
    return registry


def strategy_contract_to_dict(contract: StrategyContract) -> Dict[str, object]:
    return {
        "strategy_id": contract.strategy_id,
        "version": contract.version,
        "display_name": contract.display_name,
        "family": contract.family,
        "stage": contract.stage.value,
        "source_of_truth": contract.source_of_truth,
        "owner_module": contract.owner_module,
        "candidate_id": contract.candidate_id or None,
        "parameter_hash": contract.parameter_hash or None,
        "publication_capability": contract.publication_capability.value,
        "publication_gate_id": contract.publication_gate_id or None,
        "allowed_event_classes": [item.value for item in contract.allowed_event_classes],
        "evidence_keys": list(contract.evidence_keys),
        "real_order_execution_allowed": contract.real_order_execution_allowed,
        "limitations": list(contract.limitations),
    }
