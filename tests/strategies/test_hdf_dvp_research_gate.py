from backend.strategies.hdf.dvp_research_gate import evaluate_dvp_research_gate
from backend.strategies.hdf.prospective_fibonacci import ConfirmedPivot


def pivots():
    return [
        ConfirmedPivot(1, 100.0, False, 3),
        ConfirmedPivot(5, 110.0, True, 7),
    ]


def gate(**overrides):
    args = dict(direction="BULLISH", divergence_pass=True, volume_pass=True, pattern_pass=True,
                pivots=pivots(), decision_index=10, candle_low=116.0, candle_high=116.3,
                fib_policy_promoted=False)
    args.update(overrides)
    return evaluate_dvp_research_gate(**args)


def test_rejects_before_fibonacci_when_any_core_confluence_fails():
    assert gate(divergence_pass=False).reason == "DIVERGENCE_FAIL"
    assert gate(volume_pass=False).reason == "VOLUME_FAIL"
    assert gate(pattern_pass=False).reason == "PATTERN_FAIL"


def test_fibonacci_pass_is_not_enough_while_policy_is_research_only():
    result = gate()
    assert result.fibonacci.status == "PASS"
    assert result.eligible is False
    assert result.status == "RESEARCH_ONLY"


def test_rejects_when_selected_fibonacci_leg_does_not_touch_candle():
    result = gate(candle_low=115.0, candle_high=115.5)
    assert result.eligible is False
    assert result.reason == "FIBONACCI_FAIL"


def test_only_promoted_policy_can_make_four_confluence_gate_eligible():
    result = gate(fib_policy_promoted=True)
    assert result.eligible is True
    assert result.status == "PASS"
    assert result.reason == "FOUR_CONFLUENCES_CONFIRMED"
