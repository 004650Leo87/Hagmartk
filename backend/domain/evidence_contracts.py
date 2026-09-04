from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from backend.domain.market_events import EvidenceProvenance
from backend.domain.strategy_contracts import StrategyContractRegistry, build_product_strategy_registry


@dataclass(frozen=True)
class EvidenceContract:
    evidence_key: str
    strategy_id: str
    strategy_version: str
    display_name: str
    owner_module: str
    provenance: EvidenceProvenance
    storage_kind: str
    storage_ref: str
    purpose: str
    mutation_contract: str
    research_only: bool = False
    can_support_quant_event: bool = False
    publication_gate_required: bool = True
    live_filter: str = ""
    audit_retained: bool = True
    limitations: Tuple[str, ...] = field(default_factory=tuple)

    def validation_errors(self) -> Tuple[str, ...]:
        errors = []
        for name, value in (
            ("evidence_key", self.evidence_key),
            ("strategy_id", self.strategy_id),
            ("strategy_version", self.strategy_version),
            ("display_name", self.display_name),
            ("owner_module", self.owner_module),
            ("storage_kind", self.storage_kind),
            ("storage_ref", self.storage_ref),
            ("purpose", self.purpose),
            ("mutation_contract", self.mutation_contract),
        ):
            if not str(value).strip():
                errors.append(f"MISSING_{name.upper()}")

        if self.research_only and self.can_support_quant_event:
            errors.append("RESEARCH_ONLY_CANNOT_SUPPORT_QUANT_EVENT")
        if self.can_support_quant_event and not self.publication_gate_required:
            errors.append("QUANT_SUPPORT_REQUIRES_PUBLICATION_GATE")
        return tuple(errors)


class EvidenceContractRegistry:
    def __init__(self, strategies: Optional[StrategyContractRegistry] = None) -> None:
        self._strategies = strategies or build_product_strategy_registry()
        self._contracts: Dict[str, EvidenceContract] = {}

    def register(self, contract: EvidenceContract) -> None:
        errors = contract.validation_errors()
        if errors:
            raise ValueError(f"Invalid evidence contract: {errors}")
        if self._strategies.get(contract.strategy_id, contract.strategy_version) is None:
            raise ValueError(
                f"Evidence references unregistered strategy: {contract.strategy_id}:{contract.strategy_version}"
            )
        if contract.evidence_key in self._contracts:
            raise ValueError(f"Duplicate evidence contract: {contract.evidence_key}")
        self._contracts[contract.evidence_key] = contract

    def get(self, evidence_key: str) -> Optional[EvidenceContract]:
        return self._contracts.get(evidence_key)

    def list_all(self) -> Tuple[EvidenceContract, ...]:
        return tuple(sorted(self._contracts.values(), key=lambda item: item.evidence_key))


def build_product_evidence_registry() -> EvidenceContractRegistry:
    strategies = build_product_strategy_registry()
    registry = EvidenceContractRegistry(strategies=strategies)

    registry.register(
        EvidenceContract(
            evidence_key="HDF_SHADOW_EVIDENCE_V1",
            strategy_id="hagmartk_divergence_flow",
            strategy_version="1.0.0",
            display_name="HDF Shadow Evidence",
            owner_module="backend.services.shadow_store",
            provenance=EvidenceProvenance.SHADOW,
            storage_kind="SQLITE_TABLE",
            storage_ref="shadow_hdf_evidence",
            purpose="Prospective HDF divergence/volume/pattern evidence and lifecycle linkage.",
            mutation_contract="UPSERT_IDENTITY_STABLE_LIFECYCLE_EVOLVES",
            research_only=False,
            can_support_quant_event=True,
            publication_gate_required=True,
            live_filter="source=LIVE_PROSPECTIVE AND is_test=0",
            audit_retained=True,
        )
    )

    registry.register(
        EvidenceContract(
            evidence_key="HDF_FIBONACCI_RESEARCH_V1",
            strategy_id="hagmartk_divergence_flow",
            strategy_version="1.0.0",
            display_name="HDF Fibonacci Prospective Research",
            owner_module="backend.services.fibonacci_prospective_telemetry",
            provenance=EvidenceProvenance.RESEARCH,
            storage_kind="SQLITE_TABLE",
            storage_ref="shadow_fibonacci_telemetry",
            purpose="Research-only decision snapshots and post-decision Fibonacci outcomes.",
            mutation_contract="DECISION_SNAPSHOT_IMMUTABLE_OUTCOMES_EVOLVE",
            research_only=True,
            can_support_quant_event=False,
            publication_gate_required=True,
            live_filter="source=LIVE_PROSPECTIVE AND is_test=0",
            audit_retained=True,
            limitations=(
                "Automatic swing selector remains a HAGMARTK research hypothesis.",
                "No automatic strategy promotion authority.",
            ),
        )
    )

    registry.register(
        EvidenceContract(
            evidence_key="CYCLE_THEORY_V111_FIDELITY_EVIDENCE",
            strategy_id="cycle_theory_v111_fidelity",
            strategy_version="111.00",
            display_name="Cycle Theory V111 Fidelity Evidence",
            owner_module="backend.strategies.cycle_theory",
            provenance=EvidenceProvenance.RESEARCH,
            storage_kind="GIT_AUDIT_DOCS_AND_TESTS",
            storage_ref="docs/CYCLE_THEORY_V111_PARITY_MATRIX.md + tests/strategies/test_cycle_theory_*",
            purpose="Read-only source/parity/fidelity evidence for the V111 research port.",
            mutation_contract="APPEND_VERSIONED_GIT_EVIDENCE",
            research_only=True,
            can_support_quant_event=False,
            publication_gate_required=True,
            audit_retained=True,
            limitations=(
                "Execution-sensitive parity remains partial/modelled at the current safe boundary.",
                "No real-order execution or profitability claim is authorized.",
            ),
        )
    )
    return registry


def evidence_contract_to_dict(contract: EvidenceContract) -> Dict[str, object]:
    return {
        "evidence_key": contract.evidence_key,
        "strategy_id": contract.strategy_id,
        "strategy_version": contract.strategy_version,
        "display_name": contract.display_name,
        "owner_module": contract.owner_module,
        "provenance": contract.provenance.value,
        "storage_kind": contract.storage_kind,
        "storage_ref": contract.storage_ref,
        "purpose": contract.purpose,
        "mutation_contract": contract.mutation_contract,
        "research_only": contract.research_only,
        "can_support_quant_event": contract.can_support_quant_event,
        "publication_gate_required": contract.publication_gate_required,
        "live_filter": contract.live_filter or None,
        "audit_retained": contract.audit_retained,
        "limitations": list(contract.limitations),
    }
