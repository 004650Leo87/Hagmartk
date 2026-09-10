from datetime import datetime, timezone

import pytest

from backend.strategies.cycle_theory.public_reference import (
    build_opening_channel,
    detect_first_breakout_close,
    project_accumulated_cycles,
)


def _bar(minute, low, high, close=None):
    return {
        "time": datetime(2026, 9, 6, 21, minute, tzinfo=timezone.utc).isoformat(),
        "open": (low + high) / 2,
        "high": high,
        "low": low,
        "close": close if close is not None else (low + high) / 2,
    }


def test_opening_channel_is_first_four_contiguous_m15_bars():
    channel = build_opening_channel([
        _bar(0, 100, 104), _bar(15, 99, 103),
        _bar(30, 101, 105), _bar(45, 100, 102),
    ])
    assert channel.low == 99
    assert channel.high == 105
    assert channel.height == 6
    assert (channel.end - channel.start).total_seconds() == 3600

def test_accumulated_geometry_projects_c1_c2_c3_up():
    channel = build_opening_channel([
        _bar(0, 100, 104), _bar(15, 100, 104),
        _bar(30, 100, 104), _bar(45, 100, 104),
    ])
    geometry = project_accumulated_cycles(channel, "UP", 3)
    assert [(c.name, c.low, c.high, c.size) for c in geometry.cycles] == [
        ("C1", 104, 108, 4),
        ("C2", 108, 116, 8),
        ("C3", 116, 132, 16),
    ]
    assert geometry.cycles[2].midpoint == 124


def test_accumulated_geometry_is_symmetric_down():
    channel = build_opening_channel([
        _bar(0, 100, 104), _bar(15, 100, 104),
        _bar(30, 100, 104), _bar(45, 100, 104),
    ])
    geometry = project_accumulated_cycles(channel, "DOWN", 3)
    assert [(c.low, c.high) for c in geometry.cycles] == [
        (96, 100), (88, 96), (72, 88),
    ]

def test_breakout_requires_close_outside_opening_channel():
    channel = build_opening_channel([
        _bar(0, 100, 104), _bar(15, 100, 104),
        _bar(30, 100, 104), _bar(45, 100, 104),
    ])
    after = [
        {**_bar(0, 99, 105, close=103), "time": "2026-09-06T22:00:00+00:00"},
        {**_bar(15, 103, 106, close=105), "time": "2026-09-06T22:15:00+00:00"},
    ]
    assert detect_first_breakout_close(channel, after) == "UP"


def test_opening_channel_rejects_non_contiguous_bars():
    rows = [
        _bar(0, 100, 104), _bar(15, 100, 104),
        _bar(45, 100, 104),
        {**_bar(0, 100, 104), "time": "2026-09-06T22:00:00+00:00"},
    ]
    with pytest.raises(ValueError, match="contiguous"):
        build_opening_channel(rows)