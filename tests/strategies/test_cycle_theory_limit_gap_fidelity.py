"""Gate 3K: bound pending-limit fill behavior when a quote gaps through price.

These tests document the current research model. They do not claim MT5 parity.
"""
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.tick_execution import CycleTheoryTickExecutionHarness

MAGIC = 111


def test_buy_limit_gap_through_is_filled_at_submitted_limit_price():
    broker = MockBroker("EURUSD")
    broker.buy_limit(1.0, 1.1000, 1.0900, 1.1200, MAGIC)
    events = CycleTheoryTickExecutionHarness(broker).process_tick(1.0980, 1.0982)
    assert events[0].kind == "LIMIT_FILLED"
    assert events[0].price == 1.1000
    assert broker.positions[0].price_open == 1.1000


def test_sell_limit_gap_through_is_filled_at_submitted_limit_price():
    broker = MockBroker("EURUSD")
    broker.sell_limit(1.0, 1.1000, 1.1100, 1.0800, MAGIC)
    events = CycleTheoryTickExecutionHarness(broker).process_tick(1.1020, 1.1022)
    assert events[0].kind == "LIMIT_FILLED"
    assert events[0].price == 1.1000
    assert broker.positions[0].price_open == 1.1000
