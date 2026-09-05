from datetime import datetime, timezone

import pytest

from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock


def test_scoped_offset_converts_real_utc_to_v111_server_wall_clock():
    clock = CycleTheoryBrokerClock.from_runtime_scope({"broker_time_offset_hours": 3})
    observed_utc = datetime(2026, 9, 4, 1, 30, tzinfo=timezone.utc)

    server_time = clock.utc_to_server_naive(observed_utc)

    assert server_time == datetime(2026, 9, 4, 4, 30)
    assert server_time.tzinfo is None
    assert clock.server_naive_to_utc(server_time) == observed_utc


def test_conversion_refuses_silent_timezone_stripping():
    clock = CycleTheoryBrokerClock(offset_hours=3)
    with pytest.raises(ValueError, match="timezone-aware"):
        clock.utc_to_server_naive(datetime(2026, 9, 4, 1, 30))


def test_runtime_scope_requires_explicit_valid_offset():
    with pytest.raises(ValueError, match="explicit"):
        CycleTheoryBrokerClock.from_runtime_scope({})
    with pytest.raises(ValueError, match=r"between -14 and \+14"):
        CycleTheoryBrokerClock.from_runtime_scope({"broker_time_offset_hours": 15})
