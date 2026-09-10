import pytest

from backend.strategies.ddix.dmi_reference import (
    DidiTrendState,
    DmiDirection,
    DmiSnapshot,
    classify_adx_kick_candidate,
    classify_didi_dmi_context,
)


def test_bullish_trend_present_when_didi_no_trend_rules_are_false():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(34.0, 19.0, 31.0),
        DmiSnapshot(36.0, 18.0, 33.0),
    )
    assert evidence.direction is DmiDirection.BULLISH
    assert evidence.trend_state is DidiTrendState.TREND_PRESENT
    assert evidence.trend_present is True
    assert evidence.adx_rising is True
    assert evidence.reason_codes == ("TREND_PRESENT_BY_DIDI_RULE",)


def test_adx_below_both_di_is_no_trend():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(39.0, 35.0, 30.0),
        DmiSnapshot(40.0, 36.0, 31.0),
    )
    assert evidence.trend_present is False
    assert evidence.trend_state is DidiTrendState.NO_TREND
    assert evidence.no_trend_adx_below_both is True
    assert "ADX_BELOW_BOTH_DI" in evidence.reason_codes


def test_falling_adx_at_or_below_32_is_no_trend():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(35.0, 20.0, 34.0),
        DmiSnapshot(36.0, 19.0, 32.0),
    )
    assert evidence.direction is DmiDirection.BULLISH
    assert evidence.adx_falling is True
    assert evidence.no_trend_adx_falling_le_level is True
    assert evidence.trend_present is False


def test_falling_adx_above_32_still_has_trend_by_didi_rule():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(40.0, 18.0, 40.0),
        DmiSnapshot(42.0, 17.0, 35.0),
    )
    assert evidence.adx_falling is True
    assert evidence.trend_present is True
    assert evidence.trend_state is DidiTrendState.TREND_PRESENT


def test_bearish_direction_uses_di_minus_above_di_plus():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(20.0, 34.0, 31.0),
        DmiSnapshot(18.0, 36.0, 34.0),
    )
    assert evidence.direction is DmiDirection.BEARISH
    assert evidence.trend_present is True


def test_equal_di_values_are_flat_direction():
    evidence = classify_didi_dmi_context(
        DmiSnapshot(25.0, 25.0, 35.0),
        DmiSnapshot(25.0, 25.0, 36.0),
    )
    assert evidence.direction is DmiDirection.FLAT


def test_adx_kick_requires_rise_then_fall():
    kick = classify_adx_kick_candidate(28.0, 36.0, 33.0)
    assert kick.detected is True
    no_kick = classify_adx_kick_candidate(28.0, 31.0, 34.0)
    assert no_kick.detected is False


def test_dmi_invalid_values_fail_closed():
    with pytest.raises(ValueError, match="DDIX_DMI_VALUE_OUT_OF_RANGE"):
        classify_didi_dmi_context(
            DmiSnapshot(101.0, 10.0, 20.0),
            DmiSnapshot(30.0, 10.0, 20.0),
        )
    with pytest.raises(ValueError, match="DDIX_DMI_LEVEL_INVALID"):
        classify_didi_dmi_context(
            DmiSnapshot(30.0, 10.0, 20.0),
            DmiSnapshot(30.0, 10.0, 20.0),
            no_trend_level=-1.0,
        )
