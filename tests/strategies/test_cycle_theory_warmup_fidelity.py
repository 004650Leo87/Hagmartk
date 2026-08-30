"""Gate 3L: warmup semantics for Cycle Theory V111 replay."""
from datetime import datetime, timedelta
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay, ReplayBar
from backend.strategies.cycle_theory.inputs import baseline_inputs


def _bars(count):
    start = datetime(2020, 1, 1)
    return [ReplayBar(start + timedelta(minutes=5*i), 1.1+i*.0001, 1.101+i*.0001,
                      1.099+i*.0001, 1.1005+i*.0001, 10) for i in range(count)]


def test_warmup_publishes_history_without_running_strategy_ticks(monkeypatch):
    bars = _bars(20)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), MockBroker("EURUSD", point=.0001, digits=4))
    calls = []
    monkeypatch.setattr(replay.adapter, "on_tick", lambda: calls.append(replay.broker.now))
    result = replay.run(bars, warmup_bars=14)
    assert result.evaluation_bars == 6
    assert len(calls) == 24
    assert calls[0] == bars[14].time


def test_default_context_boundary_has_valid_atr_history(monkeypatch):
    bars = _bars(20)
    replay = CycleTheoryHistoricalReplay(
        "EURUSD", "M5", baseline_inputs(), MockBroker("EURUSD", point=.0001, digits=4)
    )
    snapshots = []
    def capture():
        snapshots.append((len(replay.raw_broker.bars["M5"]), replay.raw_broker.atr_value))
    monkeypatch.setattr(replay.adapter, "on_tick", capture)
    replay.run(bars, warmup_bars=14)
    # First evaluated candle is index 14: 14 pre-existing bars + current forming bar.
    assert snapshots[0][0] == 15
    assert snapshots[0][1] > 0.0
