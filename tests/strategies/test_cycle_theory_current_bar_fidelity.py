"""Gate 3J: current-bar OHLC anti-lookahead contract."""
from datetime import datetime, timedelta

from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay, ReplayBar
from backend.strategies.cycle_theory.inputs import baseline_inputs


def _bar(i, open_, high, low, close):
    return ReplayBar(datetime(2020, 1, 1) + timedelta(minutes=5*i), open_, high, low, close, 10)


def test_current_bar_ohlc_is_published_progressively(monkeypatch):
    history = [_bar(i, 1.1000, 1.1010, 1.0990, 1.1000) for i in range(14)]
    current = _bar(14, 1.1000, 1.1500, 1.0990, 1.1200)
    broker = MockBroker("EURUSD", point=0.0001, digits=4)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker)
    seen = []

    def capture():
        seen.append((broker.i_high("M5", 0), broker.i_low("M5", 0), broker.i_close("M5", 0)))

    monkeypatch.setattr(replay.adapter, "on_tick", capture)
    replay.run(history + [current], warmup_bars=14)

    assert seen[0] == (current.open, current.open, current.open)
    assert seen[-1] == (current.high, current.low, current.close)
    assert seen[0] != (current.high, current.low, current.close)
