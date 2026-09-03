import pandas as pd

from tools.research_dvp_htf_context_lag_diagnostic import first_parent_terminal
from tools.research_dvp_htf_fibonacci_context import inspect_parent_level


def candles(*pairs):
    return pd.DataFrame([{"high": high, "low": low} for high, low in pairs])


def test_prior_target_and_stop_same_bar_is_ambiguous():
    df = candles((110.0, 90.0), (105.0, 95.0))
    status = inspect_parent_level(df, 0, 1, "BULLISH", 95.0, 105.0)
    assert status == "AMBIGUOUS_TARGET_STOP_PRIOR_BAR"


def test_child_target_and_stop_same_bar_is_ambiguous():
    df = candles((104.0, 96.0), (110.0, 90.0))
    status = inspect_parent_level(df, 0, 1, "BULLISH", 95.0, 105.0)
    assert status == "AMBIGUOUS_TARGET_STOP_CHILD_BAR"


def test_parent_terminal_reports_target_first_before_later_stop():
    df = candles((106.0, 100.0), (104.0, 94.0))
    state, index = first_parent_terminal(df, 0, "BULLISH", 95.0, 105.0)
    assert (state, index) == ("TARGET_FIRST", 0)


def test_parent_terminal_reports_stop_first_before_later_target():
    df = candles((104.0, 94.0), (106.0, 100.0))
    state, index = first_parent_terminal(df, 0, "BULLISH", 95.0, 105.0)
    assert (state, index) == ("STOP_FIRST", 0)
