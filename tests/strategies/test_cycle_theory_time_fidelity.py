"""Gate 3G: time-domain fidelity contracts for Cycle Theory V111."""
from datetime import datetime, timezone

from backend.strategies.cycle_theory.historical_replay import _datetime


def test_replay_rejects_timezone_aware_timestamp_without_server_time_contract():
    """Offset-aware data must not be silently relabelled as broker server time."""
    source = datetime(2026, 1, 5, 13, 0, tzinfo=timezone.utc)
    try:
        _datetime(source)
    except ValueError as exc:
        assert "server time" in str(exc).lower()
    else:
        raise AssertionError("timezone-aware timestamp was silently accepted")


def test_replay_keeps_naive_broker_server_clock_unchanged():
    source = datetime(2026, 1, 5, 9, 30)
    assert _datetime(source) == source
