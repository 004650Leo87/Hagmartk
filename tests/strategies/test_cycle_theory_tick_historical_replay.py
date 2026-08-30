from datetime import datetime, timedelta

from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import ReplayBar
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.tick_historical_replay import (
    CycleTheoryTickHistoricalReplay,
    ReplayTick,
)


def _bars():
    start = datetime(2026, 1, 5, 9, 0)
    return [
        ReplayBar(start + timedelta(minutes=i), 1.1000, 1.1020, 1.0980, 1.1010)
        for i in range(10)
    ]


def _ticks(bars):
    result = {}
    for bar in bars:
        result[bar.time] = [
            ReplayTick(bar.time + timedelta(seconds=5), 1.1000, 1.1002),
            ReplayTick(bar.time + timedelta(seconds=10), 1.1020, 1.1023),
            ReplayTick(bar.time + timedelta(seconds=20), 1.0980, 1.0984),
            ReplayTick(bar.time + timedelta(seconds=50), 1.1010, 1.1012),
        ]
    return result

def test_tick_replay_uses_observed_tick_order_and_spread():
    bars = _bars()
    broker = MockBroker("EURUSD")
    replay = CycleTheoryTickHistoricalReplay("EURUSD", "M1", baseline_inputs(), broker)
    observed = []
    replay.adapter.on_tick = lambda: observed.append((broker.bid, broker.ask))
    result = replay.run_ticks(bars, _ticks(bars))

    assert observed[:4] == [
        (1.1000, 1.1002),
        (1.1020, 1.1023),
        (1.0980, 1.0984),
        (1.1010, 1.1012),
    ]
    assert result.execution_model == "MT5_TICK_PATH_V1"
    assert result.spread_model == "OBSERVED_TICK_BID_ASK"
    assert result.fill_model == "TICK_QUOTES_EXACT_LEVEL_FILL_MODEL"


def test_tick_replay_does_not_fabricate_missing_bar_ticks():
    bars = _bars()
    ticks = _ticks(bars)
    ticks.pop(bars[-1].time)
    replay = CycleTheoryTickHistoricalReplay(
        "EURUSD", "M1", baseline_inputs(), MockBroker("EURUSD")
    )
    result = replay.run_ticks(bars, ticks)
    assert result.evaluation_bars == 9


def test_tick_replay_rejects_timezone_aware_tick_without_server_time_contract():
    from datetime import timezone
    bars = _bars()
    ticks = _ticks(bars)
    aware = ReplayTick(ticks[bars[0].time][0].time.replace(tzinfo=timezone.utc), 1.1, 1.1002)
    ticks[bars[0].time][0] = aware
    replay = CycleTheoryTickHistoricalReplay("EURUSD", "M1", baseline_inputs(), MockBroker("EURUSD"))
    try:
        replay.run_ticks(bars, ticks)
    except ValueError as exc:
        assert "server time" in str(exc).lower()
    else:
        raise AssertionError("timezone-aware tick was silently accepted")


def test_tick_replay_rejects_inverted_bid_ask():
    bars = _bars(); ticks = _ticks(bars)
    ticks[bars[0].time][0] = ReplayTick(ticks[bars[0].time][0].time, 1.1003, 1.1002)
    replay = CycleTheoryTickHistoricalReplay("EURUSD", "M1", baseline_inputs(), MockBroker("EURUSD"))
    try:
        replay.run_ticks(bars, ticks)
    except ValueError as exc:
        assert "ask" in str(exc).lower()
    else:
        raise AssertionError("inverted bid/ask was silently accepted")
