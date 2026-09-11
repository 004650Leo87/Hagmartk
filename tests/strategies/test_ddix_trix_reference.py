import pytest

from backend.strategies.ddix.trix_reference import (
    DDIX_TRIX_PERIOD,
    DDIX_TRIX_SIGNAL_PERIOD,
    classify_trix_cross,
    compute_trix_values,
    compute_trix_with_signal,
    ema_series,
)


def test_ddix_trix_source_supported_parameters_are_9_and_4():
    assert DDIX_TRIX_PERIOD == 9
    assert DDIX_TRIX_SIGNAL_PERIOD == 4


def test_ema_recurrence_matches_standard_alpha_formula():
    values = ema_series([1.0, 2.0, 3.0], period=3)
    assert values == pytest.approx((1.0, 1.5, 2.25))


def test_period_one_trix_reduces_exactly_to_percent_rate_of_change():
    values = compute_trix_values([100.0, 110.0, 99.0], period=1)
    assert values[0] is None
    assert values[1] == pytest.approx(10.0)
    assert values[2] == pytest.approx(-10.0)


def test_constant_price_series_has_zero_trix_after_first_bar():
    values = compute_trix_values([100.0] * 20)
    assert values[0] is None
    assert all(value == pytest.approx(0.0) for value in values[1:])


def test_signal_mode_is_explicit_and_unknown_mode_fails_closed():
    with pytest.raises(ValueError, match="DDIX_TRIX_SIGNAL_MODE_NOT_APPROVED"):
        compute_trix_with_signal([100.0, 101.0, 102.0], signal_mode="WILDER", trix_period=1)


def test_sma_signal_waits_for_full_signal_window():
    series = compute_trix_with_signal(
        [100.0, 110.0, 99.0], signal_mode="SMA", trix_period=1, signal_period=2
    )
    assert series.signal[0] is None
    assert series.signal[1] is None
    assert series.signal[2] == pytest.approx(0.0)


def test_ema_signal_uses_explicit_exponential_candidate():
    series = compute_trix_with_signal(
        [100.0, 110.0, 99.0], signal_mode="EMA", trix_period=1, signal_period=2
    )
    assert series.signal[0] is None
    assert series.signal[1] == pytest.approx(10.0)
    assert series.signal[2] == pytest.approx(-10.0 / 3.0)


def test_bullish_and_bearish_signal_crosses_are_symmetric():
    buy = classify_trix_cross(-1.0, 0.0, 1.0, 0.0)
    sell = classify_trix_cross(1.0, 0.0, -1.0, 0.0)
    assert buy.cross == "BUY_CROSS" and buy.bullish and not buy.bearish
    assert sell.cross == "SELL_CROSS" and sell.bearish and not sell.bullish


def test_no_cross_when_relative_order_does_not_change():
    evidence = classify_trix_cross(1.0, 0.0, 2.0, 0.5)
    assert evidence.cross == "NO_CROSS"
    assert evidence.bullish is False
    assert evidence.bearish is False


def test_invalid_trix_inputs_fail_closed():
    with pytest.raises(ValueError, match="DDIX_TRIX_INSUFFICIENT_HISTORY"):
        compute_trix_values([100.0])
    with pytest.raises(ValueError, match="DDIX_TRIX_PERIOD_MUST_BE_POSITIVE"):
        compute_trix_values([100.0, 101.0], period=0)
    with pytest.raises(ValueError, match="DDIX_TRIX_VALUE_NOT_FINITE"):
        compute_trix_values([100.0, float("nan")])
    with pytest.raises(ValueError, match="DDIX_TRIX_SIGNAL_PERIOD_MUST_BE_POSITIVE"):
        compute_trix_with_signal([100.0, 101.0], signal_mode="EMA", signal_period=0)
