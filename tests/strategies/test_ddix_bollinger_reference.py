import math

import pytest

from backend.strategies.ddix.bollinger_reference import (
    BollingerSnapshot,
    classify_bollinger_opening_candidate,
    compute_bollinger_snapshot,
    population_stddev,
)


def test_population_stddev_matches_metaquotes_n_denominator():
    values = list(range(1, 9))
    assert population_stddev(values) == pytest.approx(math.sqrt(5.25))


def test_ddix_bollinger_candidate_defaults_to_8_and_2():
    snapshot = compute_bollinger_snapshot(list(range(1, 9)))
    expected_std = math.sqrt(5.25)
    assert snapshot.period == 8
    assert snapshot.deviation == pytest.approx(2.0)
    assert snapshot.basis == pytest.approx(4.5)
    assert snapshot.stddev == pytest.approx(expected_std)
    assert snapshot.upper == pytest.approx(4.5 + 2.0 * expected_std)
    assert snapshot.lower == pytest.approx(4.5 - 2.0 * expected_std)
    assert snapshot.width == pytest.approx(4.0 * expected_std)
    assert snapshot.width_pct == pytest.approx((snapshot.width / 4.5) * 100.0)


def _snapshot(basis, upper, lower):
    width = upper - lower
    return BollingerSnapshot(
        basis=basis,
        stddev=width / 4.0,
        upper=upper,
        lower=lower,
        width=width,
        width_pct=(width / basis) * 100.0,
        period=8,
        deviation=2.0,
        provenance="TEST",
    )


def test_two_sided_expansion_is_mouth_opening_candidate():
    previous = _snapshot(100.0, 102.0, 98.0)
    current = _snapshot(100.0, 103.0, 97.0)
    evidence = classify_bollinger_opening_candidate(previous, current)
    assert evidence.mouth_opening_candidate is True
    assert evidence.width_increasing is True
    assert evidence.upper_rising is True
    assert evidence.lower_falling is True


def test_width_expansion_without_both_sides_is_not_mouth_opening():
    previous = _snapshot(100.0, 102.0, 98.0)
    current = _snapshot(101.5, 104.0, 99.0)
    evidence = classify_bollinger_opening_candidate(previous, current)
    assert evidence.width_increasing is True
    assert evidence.lower_falling is False
    assert evidence.mouth_opening_candidate is False
    assert "WIDTH_EXPANDING_WITHOUT_TWO_SIDED_OPENING" in evidence.reason_codes


def test_width_contraction_is_closing_candidate():
    previous = _snapshot(100.0, 103.0, 97.0)
    current = _snapshot(100.0, 102.0, 98.0)
    evidence = classify_bollinger_opening_candidate(previous, current)
    assert evidence.width_decreasing is True
    assert evidence.mouth_closing_candidate is True


def test_invalid_bollinger_inputs_fail_closed():
    with pytest.raises(ValueError, match="DDIX_BOLLINGER_INSUFFICIENT_HISTORY"):
        compute_bollinger_snapshot([1.0] * 7)
    with pytest.raises(ValueError, match="DDIX_BOLLINGER_DEVIATION_MUST_BE_POSITIVE"):
        compute_bollinger_snapshot([1.0] * 8, deviation=0.0)
    with pytest.raises(ValueError, match="DDIX_BOLLINGER_VALUE_NOT_FINITE"):
        compute_bollinger_snapshot([1.0] * 7 + [float("nan")])
