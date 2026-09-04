from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from backend.services.shadow_scanner import (
    SHADOW_ASSETS,
    SHADOW_TIMEFRAMES,
    SHADOW_TIMEFRAME_MINUTES,
    get_only_closed_candles,
)


def test_shadow_scope_is_exactly_user_approved_8_timeframes():
    assert SHADOW_TIMEFRAMES == ["M5", "M15", "M30", "H1", "H2", "H4", "D1", "W1"]
    assert len(SHADOW_ASSETS) == 13
    assert len(SHADOW_ASSETS) * len(SHADOW_TIMEFRAMES) == 104


@pytest.mark.parametrize("timeframe", SHADOW_TIMEFRAMES)
def test_closed_candle_gate_uses_real_duration_for_every_shadow_timeframe(timeframe):
    opened = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    minutes = SHADOW_TIMEFRAME_MINUTES[timeframe]
    df = pd.DataFrame([{
        "time": opened.isoformat(), "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0
    }])
    just_before = opened + timedelta(minutes=minutes) - timedelta(microseconds=1)
    exactly_closed = opened + timedelta(minutes=minutes)
    assert get_only_closed_candles(df, timeframe, just_before).empty
    assert len(get_only_closed_candles(df, timeframe, exactly_closed)) == 1


def test_unknown_shadow_timeframe_fails_closed():
    df = pd.DataFrame([{
        "time": "2026-09-01T00:00:00+00:00", "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0
    }])
    with pytest.raises(ValueError, match="Unsupported Shadow timeframe"):
        get_only_closed_candles(df, "M7", datetime(2026, 9, 1, 1, 0, tzinfo=timezone.utc))
