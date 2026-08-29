import pytest
from datetime import datetime
from backend.strategies.cycle_theory.historical_replay import (
    ReplayBar, CycleTheoryHistoricalReplay, replay_bars_from_dataframe
)
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.enums import PositionType

def mock_broker():
    return MockBroker(symbol="EURUSD", point=0.0001, digits=4)

def generate_bars(count: int, start_idx: int = 0) -> list[ReplayBar]:
    bars = []
    base_time = datetime(2020, 1, 1, 0, 0, 0)
    import datetime as dt
    for i in range(count):
        idx = start_idx + i
        t = base_time + dt.timedelta(minutes=5 * idx)
        bars.append(ReplayBar(
            time=t,
            open=1.1000 + (idx * 0.0001),
            high=1.1010 + (idx * 0.0001),
            low=1.0990 + (idx * 0.0001),
            close=1.1005 + (idx * 0.0001),
            spread_points=10
        ))
    return bars

def test_warmup_bars_not_scored():
    bars = generate_bars(15)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), mock_broker())
    result = replay.run(bars, warmup_bars=14)

    assert result.evaluation_bars == 1
    assert result.warmup_bars == 14
    assert result.completed_trades == 0
    assert result.summary.trades == 0

def test_exact_target_interval_boundaries():
    bars = generate_bars(5014)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), mock_broker())
    result = replay.run(bars, warmup_bars=14)

    assert result.evaluation_bars == 5000
    assert result.evaluation_first_time == bars[14].time
    assert result.evaluation_last_time == bars[-1].time

def test_terminal_unrealized_r_excluded_from_realized():
    bars = generate_bars(20)
    broker = mock_broker()
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker)

    def fake_on_tick():
        if len(broker.positions) == 0:
            # SL=0, TP=0 so it never closes naturally
            replay.broker.buy(1.0, 0.0, 0.0, 1)
            # Need to register the position manually if we bypass the engine
            pos = broker.positions[-1]
            # Since we set SL=0, initial risk will be None. We must set it to something manually for test purposes
            # Or we can just set an SL very far away

            # Let's use a far SL so risk is calculated
            broker.positions.clear()
            broker.deals.clear()
            replay.broker.buy(1.0, 0.5000, 2.0000, 1)

    replay.adapter.on_tick = fake_on_tick

    result = replay.run(bars, warmup_bars=0)

    assert result.open_positions == 1
    assert result.summary.trades == 0
    assert result.summary.net_r == 0.0

    assert result.terminal_unrealized_r > 0.0
    assert result.mark_to_market_net_r == result.terminal_unrealized_r

def test_mark_to_market_equals_realized_plus_unrealized():
    bars = generate_bars(20)
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), mock_broker())
    result = replay.run(bars, warmup_bars=0)

    assert result.mark_to_market_net_r == round(result.summary.net_r + result.terminal_unrealized_r, 8)

def test_no_synthetic_terminal_completed_trade_by_default():
    bars = generate_bars(20)
    broker = mock_broker()
    replay = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker)

    def fake_on_tick():
        if len(broker.positions) == 0:
            replay.broker.buy(1.0, 0.5000, 2.0000, 1)

    replay.adapter.on_tick = fake_on_tick
    result = replay.run(bars, warmup_bars=0)

    assert result.completed_trades == 0
    assert result.open_positions == 1

    record = replay.ledger.get(broker.positions[0].ticket)
    assert not record.closed
    assert record.remaining_volume == 1.0

def test_deterministic_repeated_replay():
    bars = generate_bars(50)
    broker1 = mock_broker()
    replay1 = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker1)
    res1 = replay1.run(bars, warmup_bars=14)

    broker2 = mock_broker()
    replay2 = CycleTheoryHistoricalReplay("EURUSD", "M5", baseline_inputs(), broker2)
    res2 = replay2.run(bars, warmup_bars=14)

    assert res1.summary == res2.summary
    assert res1.terminal_unrealized_r == res2.terminal_unrealized_r

