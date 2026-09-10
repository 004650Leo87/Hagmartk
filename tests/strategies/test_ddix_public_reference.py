import pytest

from backend.strategies.ddix.public_reference import (
    DidiIndexMethod,
    FalsePointKind,
    MovingAverages3820,
    NeedleDirection,
    classify_classic_needle_snapshot,
    classify_false_point_candidate,
    compute_didi_index_lines,
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


def test_bearish_classic_needle_requires_inverse_order():
    averages = MovingAverages3820(10.2, 10.5, 10.8)
    evidence = classify_classic_needle_snapshot(11.0, 10.0, averages)
    assert evidence.direction is NeedleDirection.BEARISH
    assert evidence.directional_order_valid is True


def test_snapshot_rejects_average_outside_body_or_bad_order():
    outside = classify_classic_needle_snapshot(
        10.0, 11.0, MovingAverages3820(11.1, 10.5, 10.2)
    )
    bad_order = classify_classic_needle_snapshot(
        10.0, 11.0, MovingAverages3820(10.5, 10.5, 10.2)
    )
    assert outside.direction is NeedleDirection.NONE
    assert outside.all_averages_inside_body is False
    assert bad_order.directional_order_valid is False


def test_didi_index_absolute_lines_use_ma8_as_zero_axis():
    lines = compute_didi_index_lines(MovingAverages3820(10.8, 10.5, 10.2))
    assert lines.method is DidiIndexMethod.ABSOLUTE
    assert lines.reference_axis == 0.0
    assert lines.fast_line == pytest.approx(0.3)
    assert lines.slow_line == pytest.approx(-0.3)


def test_didi_index_ratio_lines_are_zero_centered():
    lines = compute_didi_index_lines(
        MovingAverages3820(11.0, 10.0, 9.0), DidiIndexMethod.RATIO
    )
    assert lines.fast_line == pytest.approx(0.10)
    assert lines.slow_line == pytest.approx(-0.10)


def test_false_buy_candidate_is_bearish_continuation():
    previous = MovingAverages3820(9.9, 10.0, 10.4)
    current = MovingAverages3820(10.1, 10.0, 10.7)
    evidence = classify_false_point_candidate(previous, current)
    assert evidence.kind is FalsePointKind.FALSE_BUY
    assert evidence.fast_cross_up is True
    assert evidence.slow_moving_away is True
    assert evidence.continuation_bias is NeedleDirection.BEARISH


def test_false_sell_candidate_is_bullish_continuation():
    previous = MovingAverages3820(10.1, 10.0, 9.6)
    current = MovingAverages3820(9.9, 10.0, 9.3)
    evidence = classify_false_point_candidate(previous, current)
    assert evidence.kind is FalsePointKind.FALSE_SELL
    assert evidence.fast_cross_down is True
    assert evidence.slow_moving_away is True
    assert evidence.continuation_bias is NeedleDirection.BULLISH


def test_false_point_rejects_slow_line_moving_toward_reference():
    previous = MovingAverages3820(9.9, 10.0, 10.7)
    current = MovingAverages3820(10.1, 10.0, 10.4)
    evidence = classify_false_point_candidate(previous, current)
    assert evidence.kind is FalsePointKind.NONE
    assert evidence.fast_cross_up is True
    assert evidence.slow_moving_away is False


def test_invalid_input_is_fail_closed():
    with pytest.raises(ValueError, match="DDIX_INSUFFICIENT_HISTORY"):
        compute_moving_averages_3_8_20([1.0] * 19)
    with pytest.raises(ValueError, match="DDIX_REFERENCE_AVERAGE_ZERO"):
        compute_didi_index_lines(
            MovingAverages3820(1.0, 0.0, -1.0), DidiIndexMethod.RATIO
        )
    with pytest.raises(ValueError, match="DDIX_VALUE_NOT_FINITE"):
        simple_moving_average([1.0] * 19 + [float("nan")], 20)
