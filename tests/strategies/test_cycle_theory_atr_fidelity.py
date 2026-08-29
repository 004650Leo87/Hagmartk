"""Gate 3F: ATR fidelity and anti-lookahead contracts."""
from datetime import datetime, timedelta

from backend.strategies.cycle_theory.historical_replay import ReplayBar, _atr


def _bar(i, high, low, close=1.1000):
    return ReplayBar(datetime(2020, 1, 1) + timedelta(minutes=5*i), 1.1000, high, low, close, 10)


def test_atr_is_rolling_simple_average_of_true_range():
    bars = [_bar(i, 1.1000 + (i + 1) * 0.0001, 1.1000) for i in range(16)]
    period = 5
    trs = []
    for i in range(len(bars) - period, len(bars)):
        prev = bars[i - 1].close
        cur = bars[i]
        trs.append(max(cur.high-cur.low, abs(cur.high-prev), abs(cur.low-prev)))
    assert _atr(bars, period) == sum(trs) / period


def test_completed_bar_atr_must_not_be_used_at_current_bar_open():
    history = [_bar(i, 1.1010, 1.0990) for i in range(14)]
    future_complete = _bar(14, 1.1500, 1.0990, 1.1200)
    open_snapshot = _bar(14, 1.1000, 1.1000, 1.1000)

    final_bar_atr = _atr(history + [future_complete], 14)
    open_time_atr = _atr(history + [open_snapshot], 14)

    # A replay tick at the open may know only the range observed so far.
    assert final_bar_atr != open_time_atr
    assert final_bar_atr > open_time_atr


def test_replay_publishes_progressive_atr_inside_current_bar(monkeypatch):
    from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay
    from backend.strategies.cycle_theory.broker import MockBroker
    from backend.strategies.cycle_theory.inputs import baseline_inputs

    history = [_bar(i, 1.1010, 1.0990) for i in range(14)]
    current = _bar(14, 1.1500, 1.0990, 1.1200)
    broker = MockBroker(symbol="EURUSD", point=0.0001, digits=4)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker)
    observed = []

    monkeypatch.setattr(replay.adapter, "on_tick", lambda: observed.append(broker.atr_value))
    replay.run(history + [current], warmup_bars=14)

    open_snapshot = ReplayBar(current.time, current.open, current.open, current.open, current.open, current.spread_points)
    assert observed[0] == _atr(history + [open_snapshot], replay.inputs.atr_period)
    assert observed[-1] == _atr(history + [current], replay.inputs.atr_period)
    assert observed[0] < observed[-1]
