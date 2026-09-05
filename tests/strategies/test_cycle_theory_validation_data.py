from datetime import datetime, timezone

import pytest

from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_data import (
    closed_normalized_candles,
    server_replay_bars,
)


def _row(time: str, close: float = 1.1) -> dict:
    return {
        "time": time,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": close,
        "spread": 2,
    }


def test_closed_candle_gate_excludes_forming_and_future_candles():
    now = datetime(2026, 9, 4, 20, 17, tzinfo=timezone.utc)
    rows = [
        _row("2026-09-04T20:00:00+00:00"),
        _row("2026-09-04T20:15:00+00:00"),
        _row("2026-09-04T20:30:00+00:00"),
    ]
    closed = closed_normalized_candles(rows, "M15", now_utc=now)
    assert [row["time"] for row in closed] == ["2026-09-04T20:00:00+00:00"]


def test_closed_candle_gate_rejects_unknown_tf_and_naive_time_domain():
    now = datetime(2026, 9, 4, 20, 17, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        closed_normalized_candles([_row("2026-09-04T20:00:00+00:00")], "BAD", now)
    with pytest.raises(ValueError, match="timezone-aware"):
        closed_normalized_candles([_row("2026-09-04T20:00:00")], "M15", now)
    with pytest.raises(ValueError, match="timezone-aware"):
        closed_normalized_candles(
            [_row("2026-09-04T20:00:00+00:00")],
            "M15",
            datetime(2026, 9, 4, 20, 17),
        )


def test_server_replay_bars_apply_explicit_broker_clock_offset():
    clock = CycleTheoryBrokerClock(offset_hours=3)
    bars = server_replay_bars([_row("2026-09-04T20:00:00+00:00")], clock)
    assert len(bars) == 1
    assert bars[0].time == datetime(2026, 9, 4, 23, 0)
    assert bars[0].time.tzinfo is None
    assert bars[0].spread_points == 2
