import math

import pytest

from backend.strategies.ddix.dmi_wilder import (
    OhlcBar,
    WilderDmiStream,
    calculate_metaquotes_wilder_batch,
    calculate_metaquotes_wilder_streaming,
)


def _quantinsti_period5_fixture():
    highs = [90, 95, 105, 120, 140, 165, 195, 230, 270, 315, 365]
    lows = [82, 85, 93, 106, 124, 147, 175, 208, 246, 289, 337]
    closes = [87, 87, 97, 114, 133, 157, 186, 223, 264, 311, 350]
    return tuple(OhlcBar(h, l, c) for h, l, c in zip(highs, lows, closes))


def test_quantinsti_published_period5_directional_values():
    points = calculate_metaquotes_wilder_batch(_quantinsti_period5_fixture(), period=5)
    expected_plus_di = {
        5: 68.80733945,
        6: 71.88498403,
        7: 74.22308546,
        8: 77.37420531,
        9: 80.43684038,
        10: 83.74053399,
    }
    for index, expected in expected_plus_di.items():
        assert points[index].di_plus == pytest.approx(expected, rel=1e-9, abs=1e-9)
        assert points[index].di_minus == pytest.approx(0.0, abs=1e-12)
        assert points[index].dx == pytest.approx(100.0, abs=1e-12)
    assert points[9].adx == pytest.approx(100.0, abs=1e-12)
    assert points[10].adx == pytest.approx(100.0, abs=1e-12)


def _mixed_fixture(count=80):
    bars = []
    price = 100.0
    for i in range(count):
        drift = ((i % 9) - 4) * 0.13 + (0.22 if (i // 7) % 2 == 0 else -0.17)
        close = price + drift
        high = max(price, close) + 0.35 + (i % 3) * 0.04
        low = min(price, close) - 0.28 - (i % 4) * 0.03
        bars.append(OhlcBar(high=high, low=low, close=close))
        price = close
    return tuple(bars)


def _assert_optional_close(a, b):
    if a is None or b is None:
        assert a is b
    else:
        assert a == pytest.approx(b, rel=1e-12, abs=1e-12)

def test_batch_and_streaming_implementations_match_bar_by_bar():
    bars = _mixed_fixture()
    batch = calculate_metaquotes_wilder_batch(bars, period=8)
    streamed = calculate_metaquotes_wilder_streaming(bars, period=8)
    assert len(batch) == len(streamed)
    for left, right in zip(batch, streamed):
        assert left.index == right.index
        for field in (
            "tr", "plus_dm", "minus_dm", "atr_smma", "plus_dm_smma",
            "minus_dm_smma", "di_plus", "di_minus", "dx", "adx",
        ):
            _assert_optional_close(getattr(left, field), getattr(right, field))


def test_first_adx_is_available_at_two_periods_minus_one():
    points = calculate_metaquotes_wilder_batch(_mixed_fixture(40), period=8)
    assert all(point.adx is None for point in points[:15])
    assert points[15].adx is not None


def test_stream_object_matches_streaming_wrapper():
    bars = _mixed_fixture(30)
    engine = WilderDmiStream(period=8)
    direct = tuple(engine.update(bar) for bar in bars)
    wrapped = calculate_metaquotes_wilder_streaming(bars, period=8)
    assert direct == wrapped

def test_metaquotes_published_raw_dm_allows_independent_positive_moves():
    bars = (
        OhlcBar(high=10.0, low=5.0, close=7.0),
        OhlcBar(high=11.0, low=4.0, close=7.5),
    )
    point = calculate_metaquotes_wilder_batch(bars, period=1)[1]
    assert point.plus_dm == pytest.approx(1.0)
    assert point.minus_dm == pytest.approx(1.0)
    assert point.di_plus == pytest.approx(point.di_minus)
    assert point.dx == pytest.approx(0.0)


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError, match="DDIX_WILDER_PERIOD_INVALID"):
        calculate_metaquotes_wilder_batch(_mixed_fixture(10), period=0)
    with pytest.raises(ValueError, match="DDIX_WILDER_HIGH_BELOW_LOW"):
        calculate_metaquotes_wilder_batch((OhlcBar(1.0, 2.0, 1.5),), period=8)
    with pytest.raises(ValueError, match="DDIX_WILDER_VALUE_NOT_FINITE"):
        calculate_metaquotes_wilder_batch((OhlcBar(math.nan, 1.0, 1.5),), period=8)
