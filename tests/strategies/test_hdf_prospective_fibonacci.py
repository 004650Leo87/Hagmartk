from backend.strategies.hdf.prospective_fibonacci import (
    ConfirmedPivot, audit_latest_completed_leg, select_latest_completed_leg,
)


def p(i, price, high, confirmed=None):
    return ConfirmedPivot(i, price, high, i + 2 if confirmed is None else confirmed)


def test_ignores_pivot_not_known_at_decision_time():
    pivots = [p(1, 100, False), p(5, 110, True), p(8, 105, False), p(10, 120, True, confirmed=13)]
    a, b = select_latest_completed_leg(direction="BULLISH", pivots=pivots, decision_index=12)
    assert (a.index, b.index) == (1, 5)


def test_latest_completed_bullish_leg_is_deterministic():
    pivots = [p(1, 100, False), p(5, 110, True), p(8, 105, False), p(12, 115, True)]
    a, b = select_latest_completed_leg(direction="BULLISH", pivots=pivots, decision_index=20)
    assert (a.index, b.index) == (8, 12)


def test_latest_completed_bearish_leg_is_deterministic():
    pivots = [p(1, 120, True), p(5, 110, False), p(8, 115, True), p(12, 100, False)]
    a, b = select_latest_completed_leg(direction="BEARISH", pivots=pivots, decision_index=20)
    assert (a.index, b.index) == (8, 12)


def test_pass_requires_level_inside_real_candle_range():
    pivots = [p(1, 100, False), p(5, 110, True)]
    # 61.8% projection = 116.18
    result = audit_latest_completed_leg(direction="BULLISH", pivots=pivots, decision_index=10,
                                        candle_low=116.0, candle_high=116.3)
    assert result.status == "PASS"
    assert result.matched_levels == (0.618,)


def test_no_arbitrary_tolerance_is_used():
    pivots = [p(1, 100, False), p(5, 110, True)]
    result = audit_latest_completed_leg(direction="BULLISH", pivots=pivots, decision_index=10,
                                        candle_low=116.19, candle_high=116.30)
    assert result.status == "FAIL"


def test_returns_unresolved_without_known_leg():
    result = audit_latest_completed_leg(direction="BULLISH", pivots=[p(5, 110, True)], decision_index=10,
                                        candle_low=100, candle_high=120)
    assert result.status == "UNRESOLVED"
