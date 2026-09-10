import pytest

from backend.strategies.ddix.public_reference import (
    MovingAverages3820,
    NeedleDirection,
    classify_classic_needle_snapshot,
    compute_moving_averages_3_8_20,
    simple_moving_average,
)


def test_simple_moving_average_uses_latest_window():
    values = list(range(1, 21))
    assert simple_moving_average(values, 3) == pytest.approx(19.0)
    assert simple_moving_average(values, 8) == pytest.approx(16.5)
    assert simple_moving_average(values, 20) == pytest.approx(10.5)


def test_compute_3_8_20_reference_values():
    averages = compute_moving_averages_3_8_20(list(range(1, 21)))
    assert averages.fast_3 == pytest.approx(19.0)
    assert averages.reference_8 == pytest.approx(16.5)
    assert averages.slow_20 == pytest.approx(10.5)


def test_bullish_classic_needle_requires_all_three_inside_body():
    averages = MovingAverages3820(10.8, 10.5, 10.2)
    evidence = classify_classic_needle_snapshot(10.0, 11.0, averages)
    assert evidence.direction is NeedleDirection.BULLISH
    assert evidence.all_averages_inside_body is True
    assert evidence.directional_order_valid is True


def test_bearish_classic_needle_requires_inverse_order():
    averages = MovingAverages3820(10.2, 10.5, 10.8)
    evidence = classify_classic_needle_snapshot(11.0, 10.0, averages)
    assert evidence.direction is NeedleDirection.BEARISH
    assert evidence.all_averages_inside_body is True
    assert evidence.directional_order_valid is True


def test_snapshot_rejects_average_outside_body():
    averages = MovingAverages3820(11.1, 10.5, 10.2)
    evidence = classify_classic_needle_snapshot(10.0, 11.0, averages)
    assert evidence.direction is NeedleDirection.NONE
    assert evidence.all_averages_inside_body is False


def test_snapshot_rejects_non_directional_order():
    averages = MovingAverages3820(10.5, 10.5, 10.2)
    evidence = classify_classic_needle_snapshot(10.0, 11.0, averages)
    assert evidence.direction is NeedleDirection.NONE
    assert evidence.directional_order_valid is False


def test_invalid_input_is_fail_closed():
    with pytest.raises(ValueError, match="DDIX_INSUFFICIENT_HISTORY"):
        compute_moving_averages_3_8_20([1.0] * 19)
    with pytest.raises(ValueError, match="DDIX_TOLERANCE_MUST_BE_NONNEGATIVE"):
        classify_classic_needle_snapshot(
            10.0,
            11.0,
            MovingAverages3820(10.8, 10.5, 10.2),
            tolerance=-0.1,
        )
    with pytest.raises(ValueError, match="DDIX_VALUE_NOT_FINITE"):
        simple_moving_average([1.0] * 19 + [float("nan")], 20)
