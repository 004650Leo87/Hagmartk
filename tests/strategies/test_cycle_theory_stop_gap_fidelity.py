"""Gate 3M: explicitly bound protective-exit gap behavior."""
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.tick_execution import CycleTheoryTickExecutionHarness


def _broker():
    broker = MockBroker("EURUSD", point=.0001, digits=4)
    broker.bid, broker.ask = 1.1000, 1.1002
    return broker


def test_buy_stop_gap_executes_at_stop_in_current_research_model():
    broker = _broker()
    harness = CycleTheoryTickExecutionHarness(broker)
    broker.buy(1.0, 1.0950, 1.1100, 7)
    event = harness.process_tick(bid=1.0900, ask=1.0902)[0]
    assert event.kind == "STOP_LOSS"
    assert event.price == 1.0950


def test_sell_stop_gap_executes_at_stop_in_current_research_model():
    broker = _broker()
    harness = CycleTheoryTickExecutionHarness(broker)
    broker.sell(1.0, 1.1050, 1.0900, 7)
    event = harness.process_tick(bid=1.1098, ask=1.1100)[0]
    assert event.kind == "STOP_LOSS"
    assert event.price == 1.1050
