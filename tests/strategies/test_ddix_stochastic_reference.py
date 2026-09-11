import pytest

from backend.strategies.ddix.stochastic_reference import (
    DDIX_STOCHASTIC_D_PERIOD_CANDIDATE,
    DDIX_STOCHASTIC_K_PERIOD_CANDIDATE,
    DDIX_STOCHASTIC_SLOWING_CANDIDATE,
    StochasticPoint,
    classify_stochastic_cross,
    compute_slow_stochastic,
)


def _fixture_series():
    highs = [10.0 + i for i in range(12)]
    lows = [0.0 + i for i in range(12)]
    closes = [5.0, 8.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
    return highs, lows, closes


def test_ddix_stochastic_defaults_are_8_3_3():
    assert DDIX_STOCHASTIC_K_PERIOD_CANDIDATE == 8
    assert DDIX_STOCHASTIC_D_PERIOD_CANDIDATE == 3
    assert DDIX_STOCHASTIC_SLOWING_CANDIDATE == 3


def test_metaquotes_sum_ratio_slow_k_reference_value():
    highs, lows, closes = _fixture_series()
    points = compute_slow_stochastic(highs, lows, closes)
    assert points[0].index == 9
    assert points[0].k == pytest.approx((48.0 / 51.0) * 100.0)


def test_signal_line_is_three_period_sma_of_slow_k():
    highs, lows, closes = _fixture_series()
    points = compute_slow_stochastic(highs, lows, closes)
    last = points[-1]
    assert last.index == 11
    assert last.d == pytest.approx((48.0 / 51.0) * 100.0)


def _point(index, k, d):
    zone = "OVERBOUGHT" if k >= 80.0 else "OVERSOLD" if k <= 20.0 else "NEUTRAL"
    return StochasticPoint(index=index, k=k, d=d, zone=zone, provenance="TEST")


def test_bullish_cross_is_k_crossing_above_d():
    evidence = classify_stochastic_cross(_point(1, 35.0, 40.0), _point(2, 45.0, 42.0))
    assert evidence.bullish_cross is True
    assert evidence.bearish_cross is False
    assert evidence.line_bias == "BUY"


def test_bearish_cross_is_k_crossing_below_d():
    evidence = classify_stochastic_cross(_point(1, 65.0, 60.0), _point(2, 55.0, 58.0))
    assert evidence.bearish_cross is True
    assert evidence.bullish_cross is False
    assert evidence.line_bias == "SELL"


def test_extreme_zone_is_context_not_reversal_trigger():
    evidence = classify_stochastic_cross(_point(1, 96.0, 94.0), _point(2, 98.0, 95.0))
    assert evidence.bullish_cross is False
    assert evidence.bearish_cross is False
    assert evidence.line_bias == "BUY"
    assert evidence.extreme_is_not_reversal_signal is True
    assert "EXTREME_ZONE_CONTEXT_ONLY_NOT_REVERSAL_TRIGGER" in evidence.reason_codes


def test_invalid_or_short_inputs_fail_closed():
    with pytest.raises(ValueError, match="DDIX_STOCHASTIC_INSUFFICIENT_HISTORY"):
        compute_slow_stochastic([10.0] * 10, [9.0] * 10, [9.5] * 10)
    with pytest.raises(ValueError, match="DDIX_STOCHASTIC_LENGTH_MISMATCH"):
        compute_slow_stochastic([10.0] * 12, [9.0] * 11, [9.5] * 12)
    with pytest.raises(ValueError, match="DDIX_STOCHASTIC_INVALID_OHLC"):
        compute_slow_stochastic([10.0] * 12, [9.0] * 12, [11.0] * 12)


def test_signal_cross_requires_d_line():
    with pytest.raises(ValueError, match="DDIX_STOCHASTIC_SIGNAL_LINE_UNAVAILABLE"):
        classify_stochastic_cross(_point(1, 50.0, None), _point(2, 55.0, 52.0))
