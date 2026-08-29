"""Gate 3E: prove that OHLC-only replay can be path-dependent.

These are epistemic guardrails, not strategy-performance tests.
"""
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.tick_execution import CycleTheoryTickExecutionHarness


def _events(path):
    broker = MockBroker(symbol="EURUSD", point=0.0001, digits=4)
    broker.bid, broker.ask = 1.1000, 1.1002
    harness = CycleTheoryTickExecutionHarness(broker)
    broker.buy_limit(1.0, 1.0990, 1.0980, 1.1010, 1)
    events = []
    for bid in path:
        events.extend(harness.process_tick(bid, bid + 0.0002))
    return [event.kind for event in events], broker


def test_same_bullish_ohlc_can_produce_different_trade_outcomes():
    # Same O/H/L/C, different valid intrabar chronology.
    low_first, low_first_broker = _events([1.1000, 1.0988, 1.1012, 1.1005])
    high_first, high_first_broker = _events([1.1000, 1.1012, 1.0988, 1.1005])

    assert low_first == ["LIMIT_FILLED", "TAKE_PROFIT"]
    assert high_first == ["LIMIT_FILLED"]
    assert len(low_first_broker.positions) == 0
    assert len(high_first_broker.positions) == 1


def test_ohlc_path_v0_is_not_execution_truth_for_ambiguous_bar():
    # historical_replay._path chooses low-first for this bullish candle.
    # This assertion intentionally documents that the chosen deterministic path
    # is only one of multiple market-consistent histories.
    assumed, _ = _events([1.1000, 1.0988, 1.1012, 1.1005])
    alternate, _ = _events([1.1000, 1.1012, 1.0988, 1.1005])
    assert assumed != alternate
