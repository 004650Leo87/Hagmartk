import json

import pytest

from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH
from backend.domain.market_events import MarketEventClass
from backend.domain.strategy_contracts import (
    ProductStrategyStage,
    PublicationCapability,
    StrategyContract,
    StrategyContractRegistry,
    build_product_strategy_registry,
    strategy_contract_to_dict,
)


def test_product_registry_contains_only_real_product_contracts():
    registry = build_product_strategy_registry()
    contracts = registry.list_all()
    ids = {(item.strategy_id, item.version) for item in contracts}
    assert ids == {
        ("hagmartk_divergence_flow", "1.0.0"),
        ("cycle_theory_v111_fidelity", "111.00"),
    }
    assert all("BENCHMARK" not in item.strategy_id for item in contracts)


def test_hdf_contract_preserves_canonical_candidate_hash_and_shadow_stage():
    hdf = build_product_strategy_registry().get("hagmartk_divergence_flow", "1.0.0")
    assert hdf is not None
    assert hdf.stage == ProductStrategyStage.SHADOW
    assert hdf.parameter_hash == HDF_CANDIDATE_V1_PARAMETER_HASH
    assert hdf.candidate_id == "hdf_dvp_exit_2r"
    assert hdf.publication_capability == PublicationCapability.GATED
    assert MarketEventClass.QUANT_EVENT in hdf.allowed_event_classes
    assert hdf.real_order_execution_allowed is False


def test_cycle_theory_contract_is_validation_only_and_not_publishable():
    cycle = build_product_strategy_registry().get("cycle_theory_v111_fidelity", "111.00")
    assert cycle is not None
    assert cycle.stage == ProductStrategyStage.VALIDATION
    assert cycle.candidate_id == "cycle_theory_v111_baseline"
    assert len(cycle.parameter_hash) == 64
    assert cycle.publication_capability == PublicationCapability.NONE
    assert cycle.allowed_event_classes == (MarketEventClass.RESEARCH_UPDATE,)
    assert cycle.real_order_execution_allowed is False


def test_registry_rejects_duplicate_contract():
    registry = StrategyContractRegistry()
    contract = StrategyContract(
        strategy_id="x",
        version="1",
        display_name="X",
        family="TEST",
        stage=ProductStrategyStage.RESEARCH,
        source_of_truth="test",
        owner_module="tests",
    )
    registry.register(contract)
    with pytest.raises(ValueError, match="Duplicate strategy contract"):
        registry.register(contract)


def test_shadow_contract_requires_candidate_and_hash():
    contract = StrategyContract(
        strategy_id="shadow_missing_hash",
        version="1",
        display_name="Broken Shadow",
        family="TEST",
        stage=ProductStrategyStage.SHADOW,
        source_of_truth="test",
        owner_module="tests",
        candidate_id="candidate",
        parameter_hash="",
    )
    assert "SHADOW_MISSING_PARAMETER_HASH" in contract.validation_errors()


def test_contract_serialization_is_json_safe():
    hdf = build_product_strategy_registry().get("hagmartk_divergence_flow", "1.0.0")
    assert hdf is not None
    payload = strategy_contract_to_dict(hdf)
    assert payload["stage"] == "SHADOW"
    assert payload["publication_capability"] == "GATED"
    assert payload["real_order_execution_allowed"] is False
    json.dumps(payload)
