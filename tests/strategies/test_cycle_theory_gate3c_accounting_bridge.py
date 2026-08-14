import pytest

from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.accounting_broker import (
    AccountingBrokerBridge,
)
from backend.strategies.cycle_theory.realized_ledger import (
    RealizedTradeLedger,
)


def make_bridge():
    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002

    ledger = RealizedTradeLedger(point=broker.point)

    bridge = AccountingBrokerBridge(
        broker=broker,
        ledger=ledger,
    )

    return broker, ledger, bridge


def test_market_buy_is_registered_automatically():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        1.0,
        1.0902,
        1.1202,
        7,
    )

    assert ticket is not None

    record = ledger.get(ticket)

    assert record is not None
    assert record.entry_price == pytest.approx(1.1002)
    assert record.initial_volume == 1.0
    assert record.initial_risk == pytest.approx(0.0100)


def test_market_sell_is_registered_automatically():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.sell(
        1.0,
        1.1100,
        1.0800,
        7,
    )

    assert ticket is not None

    record = ledger.get(ticket)

    assert record is not None
    assert record.entry_price == pytest.approx(1.1000)
    assert record.initial_risk == pytest.approx(0.0100)


def test_pending_order_is_registered_only_when_filled():
    broker, ledger, bridge = make_bridge()

    order_ticket = bridge.buy_limit(
        1.0,
        1.0990,
        1.0890,
        1.1190,
        7,
    )

    assert order_ticket is not None
    assert ledger.completed_records() == []

    position_ticket = bridge.fill_pending(order_ticket)

    assert position_ticket is not None

    record = ledger.get(position_ticket)

    assert record is not None
    assert record.entry_price == pytest.approx(1.0990)
    assert record.initial_risk == pytest.approx(0.0100)


def test_buy_partial_uses_current_bid_as_realized_price():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        1.0,
        1.0902,
        1.1202,
        7,
    )

    broker.bid = 1.1102
    broker.ask = 1.1104

    assert bridge.position_close_partial(
        ticket,
        0.5,
    )

    record = ledger.get(ticket)

    assert record is not None
    assert record.remaining_volume == 0.5
    assert record.legs[-1].kind == "PARTIAL"
    assert record.legs[-1].exit_price == pytest.approx(
        1.1102
    )
    assert record.legs[-1].weighted_r == pytest.approx(
        0.5
    )


def test_sell_partial_uses_current_ask_as_realized_price():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.sell(
        1.0,
        1.1100,
        1.0800,
        7,
    )

    broker.bid = 1.0898
    broker.ask = 1.0900

    assert bridge.position_close_partial(
        ticket,
        0.5,
    )

    record = ledger.get(ticket)

    assert record is not None
    assert record.remaining_volume == 0.5
    assert record.legs[-1].exit_price == pytest.approx(
        1.0900
    )
    assert record.legs[-1].weighted_r == pytest.approx(
        0.5
    )


def test_final_buy_close_uses_current_bid():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        1.0,
        1.0902,
        1.1202,
        7,
    )

    broker.bid = 1.1202
    broker.ask = 1.1204

    assert bridge.position_close(ticket)

    record = ledger.get(ticket)

    assert record is not None
    assert record.closed
    assert record.net_r == pytest.approx(2.0)


def test_final_sell_close_uses_current_ask():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.sell(
        1.0,
        1.1100,
        1.0800,
        7,
    )

    broker.bid = 1.0798
    broker.ask = 1.0800

    assert bridge.position_close(ticket)

    record = ledger.get(ticket)

    assert record is not None
    assert record.closed
    assert record.net_r == pytest.approx(2.0)


def test_position_modify_does_not_change_initial_risk():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        1.0,
        1.0902,
        1.1202,
        7,
    )

    record = ledger.get(ticket)

    assert record.initial_risk == pytest.approx(
        0.0100
    )

    assert bridge.position_modify(
        ticket,
        1.1050,
        1.1202,
    )

    assert ledger.get(ticket).initial_risk == pytest.approx(
        0.0100
    )


def test_failed_close_does_not_create_fake_ledger_leg():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        1.0,
        1.0902,
        1.1202,
        7,
    )

    before = len(ledger.get(ticket).legs)

    assert bridge.position_close(999999) is False

    after = len(ledger.get(ticket).legs)

    assert before == after


def test_partial_that_closes_entire_remaining_volume_becomes_closed():
    broker, ledger, bridge = make_bridge()

    ticket = bridge.buy(
        0.1,
        1.0902,
        1.1202,
        7,
    )

    broker.bid = 1.1102
    broker.ask = 1.1104

    assert bridge.position_close_partial(
        ticket,
        0.1,
    )

    record = ledger.get(ticket)

    assert record.closed
    assert record.remaining_volume == 0.0
    assert record.net_r == pytest.approx(1.0)