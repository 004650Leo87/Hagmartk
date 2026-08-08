from __future__ import annotations

from dataclasses import replace
import pytest

from backend.domain.candidate import (
    HDF_CANDIDATE_V1_PARAMETER_HASH,
    HDF_ROBUST_CANDIDATE_V1,
    RobustCandidateSpec,
)


def test_candidate_v1_immutability_and_hash():
    spec = HDF_ROBUST_CANDIDATE_V1
    assert spec.candidate_id == "hdf_dvp_exit_2r"
    assert spec.candidate_version == "1.0.0"
    assert spec.strategy_id == "hagmartk_divergence_flow"
    assert spec.variant == "HDF_DVP"
    assert spec.exit_policy == "EXIT_2R"
    assert spec.target_r == 2.0
    assert spec.research_status == "ROBUST_CANDIDATE"

    # Confirma validação de hash determinístico
    computed_hash = spec.compute_parameter_hash()
    assert computed_hash == HDF_CANDIDATE_V1_PARAMETER_HASH
    assert spec.validate_immutability(HDF_CANDIDATE_V1_PARAMETER_HASH) is True


def test_candidate_parameter_mutation_changes_hash():
    spec = HDF_ROBUST_CANDIDATE_V1

    # Altera um único parâmetro (ex: target_r de 2.0 para 2.5)
    mutated_spec = replace(spec, target_r=2.5)
    mutated_hash = mutated_spec.compute_parameter_hash()

    assert mutated_hash != HDF_CANDIDATE_V1_PARAMETER_HASH
    assert mutated_spec.validate_immutability(HDF_CANDIDATE_V1_PARAMETER_HASH) is False


def test_candidate_limitations_accessible():
    spec = HDF_ROBUST_CANDIDATE_V1
    assert len(spec.limitations) >= 8
    assert any("OHLC" in lim for lim in spec.limitations)
    assert any("Monte Carlo" in lim for lim in spec.limitations)
