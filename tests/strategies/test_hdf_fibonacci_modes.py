import pytest

from backend.strategies.hdf.fibonacci_modes import FibonacciConstructionMode, construct_extension
from backend.strategies.hdf.prospective_fibonacci import ConfirmedPivot


def pivot(index, price, is_high=False, confirmed=None):
    return ConfirmedPivot(index, price, is_high, index if confirmed is None else confirmed)


def test_pre_reversal_mode_preserves_source_levels_on_same_timeframe():
    out = construct_extension(mode=FibonacciConstructionMode.PRE_REVERSAL,
                              source_timeframe="M15", decision_timeframe="M15",
                              anchor_a=pivot(10, 100), anchor_b=pivot(20, 110, True))
    assert tuple(out.levels) == (0.618, 1.0, 1.618, 2.0, 2.618)
    assert out.levels[1.0] == 120.0


def test_post_reversal_mode_is_explicit_not_inferred_from_prices():
    out = construct_extension(mode=FibonacciConstructionMode.POST_REVERSAL,
                              source_timeframe="H1", decision_timeframe="H1",
                              anchor_a=pivot(30, 200, True), anchor_b=pivot(40, 180))
    assert out.mode is FibonacciConstructionMode.POST_REVERSAL
    assert out.levels[1.0] == 160.0


def test_higher_timeframe_context_requires_distinct_timeframes():
    out = construct_extension(mode=FibonacciConstructionMode.HIGHER_TIMEFRAME_CONTEXT,
                              source_timeframe="H4", decision_timeframe="M15",
                              anchor_a=pivot(1, 100), anchor_b=pivot(2, 110, True))
    assert out.source_timeframe == "H4"
    assert out.decision_timeframe == "M15"

    with pytest.raises(ValueError, match="distinct timeframes"):
        construct_extension(mode=FibonacciConstructionMode.HIGHER_TIMEFRAME_CONTEXT,
                            source_timeframe="H4", decision_timeframe="H4",
                            anchor_a=pivot(1, 100), anchor_b=pivot(2, 110, True))


def test_same_timeframe_modes_reject_cross_timeframe_silent_mix():
    with pytest.raises(ValueError, match="matching timeframes"):
        construct_extension(mode=FibonacciConstructionMode.PRE_REVERSAL,
                            source_timeframe="H4", decision_timeframe="M15",
                            anchor_a=pivot(1, 100), anchor_b=pivot(2, 110, True))
