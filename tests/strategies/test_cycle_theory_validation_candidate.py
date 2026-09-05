from backend.strategies.cycle_theory.inputs import TOTAL_INPUTS
from backend.strategies.cycle_theory.validation_candidate import (
    CYCLE_THEORY_V111_BASELINE,
    CYCLE_THEORY_V111_BASELINE_HASH,
    CYCLE_THEORY_V111_SOURCE_SHA256,
)


def test_v111_validation_baseline_is_frozen_to_source_and_30_inputs():
    assert CYCLE_THEORY_V111_BASELINE.source_version == "111.00"
    assert CYCLE_THEORY_V111_BASELINE.source_sha256 == CYCLE_THEORY_V111_SOURCE_SHA256
    assert len(CYCLE_THEORY_V111_BASELINE.parameter_payload()) == TOTAL_INPUTS == 30


def test_v111_validation_baseline_hash_is_deterministic():
    expected = "a538c37c26282ab62e36ce1c1c5c826e11aee2370c8ed4ecffdaba7f145ccf85"
    assert CYCLE_THEORY_V111_BASELINE_HASH == expected
    assert CYCLE_THEORY_V111_BASELINE.validate_immutability(expected) is True
    assert CYCLE_THEORY_V111_BASELINE.validate_immutability("0" * 64) is False
