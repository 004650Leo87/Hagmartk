from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.tick_execution import (
    CycleTheoryTickExecutionHarness,
)


def make_broker():
    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002
    return broker


def test_buy_limit_does_not_fill_above_limit():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy_limit(
        0.20, 1.0990, 1.0950, 0.0, 7
    )

    assert ticket is not None

    events = harness.process_tick(
        bid=1.0992,
        ask=1.0994,
    )

    assert events == []
    assert len(broker.pending_orders) == 1
    assert len(broker.positions) == 0


def test_buy_limit_fills_when_ask_reaches_limit():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    broker.buy_limit(
        0.20, 1.0990, 1.0950, 0.0, 7
    )

    events = harness.process_tick(
        bid=1.0988,
        ask=1.0990,
    )

    assert len(events) == 1
    assert events[0].kind == "LIMIT_FILLED"
    assert events[0].price == 1.0990

    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 1
    assert broker.positions[0].price_open == 1.0990
    assert broker.positions[0].volume == 0.20


def test_sell_limit_fills_when_bid_reaches_limit():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    broker.sell_limit(
        0.30, 1.1010, 1.1050, 0.0, 7
    )

    events = harness.process_tick(
        bid=1.1010,
        ask=1.1012,
    )

    assert len(events) == 1
    assert events[0].kind == "LIMIT_FILLED"

    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 1
    assert broker.positions[0].price_open == 1.1010
    assert broker.positions[0].volume == 0.30


def test_buy_stop_loss_closes_on_bid():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        1.0950,
        0.0,
        7,
    )

    assert ticket is not None

    events = harness.process_tick(
        bid=1.0950,
        ask=1.0952,
    )

    assert len(events) == 1
    assert events[0].kind == "STOP_LOSS"
    assert events[0].price == 1.0950
    assert len(broker.positions) == 0


def test_sell_stop_loss_closes_on_ask():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.sell(
        0.20,
        1.1050,
        0.0,
        7,
    )

    assert ticket is not None

    events = harness.process_tick(
        bid=1.1048,
        ask=1.1050,
    )

    assert len(events) == 1
    assert events[0].kind == "STOP_LOSS"
    assert len(broker.positions) == 0


def test_buy_take_profit_closes_on_bid():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        1.0950,
        1.1100,
        7,
    )

    assert ticket is not None

    events = harness.process_tick(
        bid=1.1100,
        ask=1.1102,
    )

    assert len(events) == 1
    assert events[0].kind == "TAKE_PROFIT"
    assert len(broker.positions) == 0


def test_sell_take_profit_closes_on_ask():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.sell(
        0.20,
        1.1050,
        1.0900,
        7,
    )

    assert ticket is not None

    events = harness.process_tick(
        bid=1.0898,
        ask=1.0900,
    )

    assert len(events) == 1
    assert events[0].kind == "TAKE_PROFIT"
    assert len(broker.positions) == 0


def test_same_tick_can_fill_limit_then_hit_stop():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    broker.buy_limit(
        0.20,
        1.0990,
        1.0980,
        0.0,
        7,
    )

    events = harness.process_tick(
        bid=1.0978,
        ask=1.0980,
    )

    assert [event.kind for event in events] == [
        "LIMIT_FILLED",
        "STOP_LOSS",
    ]

    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 0


def test_invalid_tick_rejects_ask_below_bid():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    try:
        harness.process_tick(
            bid=1.1002,
            ask=1.1000,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "invalid Bid/Ask tick was accepted"
        )