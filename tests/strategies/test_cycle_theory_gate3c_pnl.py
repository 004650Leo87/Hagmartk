from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.tick_execution import (
    CycleTheoryTickExecutionHarness,
)


def make_broker():
    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002
    return broker


def test_buy_stop_reports_negative_points_and_minus_one_r():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        1.0950,
        0.0,
        7,
    )
    assert ticket is not None

    pos = broker.positions[0]
    entry = pos.price_open
    initial_risk = entry - pos.sl

    events = harness.process_tick(
        bid=1.0950,
        ask=1.0952,
    )

    event = events[0]

    assert event.kind == "STOP_LOSS"
    assert event.points == round(
        (1.0950 - entry) / broker.point,
        8,
    )
    assert event.r_multiple == round(
        (1.0950 - entry) / initial_risk,
        8,
    )


def test_sell_stop_reports_negative_points_and_minus_one_r():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.sell(
        0.20,
        1.1050,
        0.0,
        7,
    )
    assert ticket is not None

    pos = broker.positions[0]
    entry = pos.price_open
    initial_risk = pos.sl - entry

    events = harness.process_tick(
        bid=1.1048,
        ask=1.1050,
    )

    event = events[0]

    assert event.kind == "STOP_LOSS"
    assert event.points == round(
        (entry - 1.1050) / broker.point,
        8,
    )
    assert event.r_multiple == round(
        (entry - 1.1050) / initial_risk,
        8,
    )


def test_buy_take_profit_reports_positive_r():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        1.0950,
        1.1100,
        7,
    )
    assert ticket is not None

    pos = broker.positions[0]
    entry = pos.price_open
    initial_risk = entry - pos.sl

    events = harness.process_tick(
        bid=1.1100,
        ask=1.1102,
    )

    event = events[0]

    assert event.kind == "TAKE_PROFIT"
    assert event.points > 0
    assert event.r_multiple == round(
        (1.1100 - entry) / initial_risk,
        8,
    )


def test_sell_take_profit_reports_positive_r():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.sell(
        0.20,
        1.1050,
        1.0900,
        7,
    )
    assert ticket is not None

    pos = broker.positions[0]
    entry = pos.price_open
    initial_risk = pos.sl - entry

    events = harness.process_tick(
        bid=1.0898,
        ask=1.0900,
    )

    event = events[0]

    assert event.kind == "TAKE_PROFIT"
    assert event.points > 0
    assert event.r_multiple == round(
        (entry - 1.0900) / initial_risk,
        8,
    )


def test_limit_fill_event_has_no_realized_pnl():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    broker.buy_limit(
        0.20,
        1.0990,
        1.0950,
        0.0,
        7,
    )

    events = harness.process_tick(
        bid=1.0988,
        ask=1.0990,
    )

    event = events[0]

    assert event.kind == "LIMIT_FILLED"
    assert event.points is None
    assert event.r_multiple is None


def test_zero_initial_risk_does_not_invent_r_multiple():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        0.0,
        1.1100,
        7,
    )
    assert ticket is not None

    events = harness.process_tick(
        bid=1.1100,
        ask=1.1102,
    )

    event = events[0]

    assert event.kind == "TAKE_PROFIT"
    assert event.points > 0
    assert event.r_multiple is None

def test_r_multiple_preserves_initial_risk_after_stop_moves():
    broker = make_broker()
    harness = CycleTheoryTickExecutionHarness(broker)

    ticket = broker.buy(
        0.20,
        1.0950,
        1.1100,
        7,
    )
    assert ticket is not None

    pos = broker.positions[0]

    original_entry = pos.price_open
    original_sl = pos.sl
    original_risk = original_entry - original_sl

    # First tick registers the ORIGINAL risk without closing.
    events = harness.process_tick(
        bid=1.1010,
        ask=1.1012,
    )

    assert events == []

    # Simulate BE/trailing moving SL above entry.
    moved_sl = original_entry + 0.0010

    assert broker.position_modify(
        ticket,
        moved_sl,
        pos.tp,
    )

    # Price returns and hits the moved stop.
    events = harness.process_tick(
        bid=moved_sl,
        ask=moved_sl + 0.0002,
    )

    assert len(events) == 1

    event = events[0]

    assert event.kind == "STOP_LOSS"
    assert event.points == round(
        (moved_sl - original_entry) / broker.point,
        8,
    )

    # Critical contract:
    # R denominator remains ORIGINAL risk, not moved stop distance.
    assert event.r_multiple == round(
        (moved_sl - original_entry) / original_risk,
        8,
    )

    assert event.r_multiple > 0