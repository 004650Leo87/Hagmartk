import json

import pytest

from backend.domain.evidence_contracts import (
    EvidenceContract,
    EvidenceContractRegistry,
    build_product_evidence_registry,
    evidence_contract_to_dict,
)
from backend.domain.market_events import EvidenceProvenance
from backend.domain.strategy_contracts import build_product_strategy_registry


def test_all_strategy_evidence_keys_resolve():
    strategies = build_product_strategy_registry()
    evidence = build_product_evidence_registry()
    for strategy in strategies.list_all():
        for key in strategy.evidence_keys:
            contract = evidence.get(key)
            assert contract is not None, f"Missing evidence contract: {key}"
            assert contract.strategy_id == strategy.strategy_id
            assert contract.strategy_version == strategy.version


def test_registry_contains_only_declared_product_evidence_contracts():
    evidence = build_product_evidence_registry()
    keys = {item.evidence_key for item in evidence.list_all()}
    assert keys == {
        "HDF_SHADOW_EVIDENCE_V1",
        "HDF_FIBONACCI_RESEARCH_V1",
        "CYCLE_THEORY_V111_FIDELITY_EVIDENCE",
    }


def test_research_only_evidence_cannot_support_quant_event():
    fib = build_product_evidence_registry().get("HDF_FIBONACCI_RESEARCH_V1")
    assert fib is not None
    assert fib.research_only is True
    assert fib.can_support_quant_event is False

    cycle = build_product_evidence_registry().get("CYCLE_THEORY_V111_FIDELITY_EVIDENCE")
    assert cycle is not None
    assert cycle.research_only is True
    assert cycle.can_support_quant_event is False


def test_shadow_evidence_can_only_support_quant_event_through_gate():
    hdf = build_product_evidence_registry().get("HDF_SHADOW_EVIDENCE_V1")
    assert hdf is not None
    assert hdf.provenance == EvidenceProvenance.SHADOW
    assert hdf.research_only is False
    assert hdf.can_support_quant_event is True
    assert hdf.publication_gate_required is True


def test_registry_rejects_evidence_for_unregistered_strategy():
    registry = EvidenceContractRegistry()
    bad = EvidenceContract(
        evidence_key="BAD",
        strategy_id="missing_strategy",
        strategy_version="1",
        display_name="Bad",
        owner_module="tests",
        provenance=EvidenceProvenance.RESEARCH,
        storage_kind="MEMORY",
        storage_ref="none",
        purpose="test",
        mutation_contract="NONE",
        research_only=True,
        can_support_quant_event=False,
    )
    with pytest.raises(ValueError, match="unregistered strategy"):
        registry.register(bad)


def test_research_only_plus_quant_support_is_invalid():
    contract = EvidenceContract(
        evidence_key="INVALID_RESEARCH_QUANT",
        strategy_id="hagmartk_divergence_flow",
        strategy_version="1.0.0",
        display_name="Invalid",
        owner_module="tests",
        provenance=EvidenceProvenance.RESEARCH,
        storage_kind="MEMORY",
        storage_ref="none",
        purpose="test",
        mutation_contract="NONE",
        research_only=True,
        can_support_quant_event=True,
        publication_gate_required=True,
    )
    assert "RESEARCH_ONLY_CANNOT_SUPPORT_QUANT_EVENT" in contract.validation_errors()


def test_evidence_contract_serialization_is_json_safe():
    contract = build_product_evidence_registry().get("HDF_SHADOW_EVIDENCE_V1")
    assert contract is not None
    payload = evidence_contract_to_dict(contract)
    assert payload["provenance"] == "SHADOW"
    assert payload["storage_ref"] == "shadow_hdf_evidence"
    assert payload["can_support_quant_event"] is True
    json.dumps(payload)
