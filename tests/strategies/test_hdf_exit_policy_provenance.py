import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.strategies.hdf.exit_policy_provenance import (
    DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE,
    ExitPolicyProvenance,
    get_exit_policy_provenance,
)


def test_frozen_candidate_exit_2r_is_hagmartk_benchmark():
    contract = get_exit_policy_provenance(HDF_ROBUST_CANDIDATE_V1.exit_policy)
    assert contract.policy_id == "EXIT_2R"
    assert contract.provenance == ExitPolicyProvenance.HAGMARTK_QUANT_BENCHMARK
    assert contract.deterministic_automation is True
    assert contract.source_described is False
    assert contract.original_divap_claim_allowed is False
    assert contract.promotion_allowed is False


def test_source_fibonacci_partials_remain_discretionary():
    contract = DIVAP_FIBONACCI_PARTIALS_SOURCE_GATE
    assert contract.source_described is True
    assert contract.deterministic_automation is False
    assert contract.promotion_allowed is False
    assert contract.original_divap_claim_allowed is False
    assert contract.target_levels == (0.618, 1.0, 1.618, 2.0, 2.618)
    assert "UNRESOLVED" in contract.allocation_policy


def test_unknown_exit_policy_has_no_implicit_provenance():
    with pytest.raises(KeyError):
        get_exit_policy_provenance("UNKNOWN_POLICY")


def test_candidate_api_exposes_exit_provenance_without_hash_change():
    from backend.api.shadow_routes import list_shadow_candidates
    from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH

    payload = list_shadow_candidates()[0]
    provenance = payload["exit_policy_provenance"]

    assert payload["parameter_hash"] == HDF_CANDIDATE_V1_PARAMETER_HASH
    assert provenance["policy_id"] == "EXIT_2R"
    assert provenance["provenance"] == "HAGMARTK_QUANT_BENCHMARK"
    assert provenance["original_divap_claim_allowed"] is False
    assert provenance["promotion_allowed"] is False


def test_shadow_event_default_hash_uses_canonical_candidate_hash():
    from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH
    from backend.domain.shadow_models import ShadowEvent

    event = ShadowEvent(event_id="hash_integrity_test")
    assert event.parameter_hash == HDF_CANDIDATE_V1_PARAMETER_HASH
    assert HDF_ROBUST_CANDIDATE_V1.validate_immutability(event.parameter_hash) is True
