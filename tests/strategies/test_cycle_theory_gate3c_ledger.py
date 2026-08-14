import pytest

from backend.strategies.cycle_theory.broker import (
    MockBroker,
    Position,
)
from backend.strategies.cycle_theory.enums import (
    PositionType,
)
from backend.strategies.cycle_theory.realized_ledger import (
    RealizedTradeLedger,
)


def make_buy_position(
    ticket=1,
    volume=1.0,
):
    return Position(
        ticket=ticket,
        symbol="EURUSD",
        magic=7,
        type=PositionType.BUY,
        volume=volume,
        price_open=1.1000,
        sl=1.0900,
        tp=1.1200,
    )


def make_sell_position(
    ticket=2,
    volume=1.0,
):
    return Position(
        ticket=ticket,
        symbol="EURUSD",
        magic=7,
        type=PositionType.SELL,
        volume=volume,
        price_open=1.1000,
        sl=1.1100,
        tp=1.0800,
    )


def test_full_buy_stop_is_minus_one_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position()
    ledger.register_position(pos)

    leg = ledger.record_final(
        pos.ticket,
        1.0900,
        "STOP_LOSS",
    )

    assert leg.raw_r == -1.0
    assert leg.weighted_r == -1.0
    assert leg.points == -100.0

    record = ledger.get(pos.ticket)

    assert record is not None
    assert record.closed
    assert record.net_r == -1.0


def test_full_buy_two_r_target_is_plus_two_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position()
    ledger.register_position(pos)

    leg = ledger.record_final(
        pos.ticket,
        1.1200,
        "TAKE_PROFIT",
    )

    assert leg.raw_r == 2.0
    assert leg.weighted_r == 2.0
    assert leg.points == 200.0

    assert ledger.get(pos.ticket).net_r == 2.0


def test_full_sell_stop_is_minus_one_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_sell_position()
    ledger.register_position(pos)

    leg = ledger.record_final(
        pos.ticket,
        1.1100,
        "STOP_LOSS",
    )

    assert leg.raw_r == -1.0
    assert leg.weighted_r == -1.0
    assert ledger.get(pos.ticket).net_r == -1.0


def test_full_sell_target_is_positive_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_sell_position()
    ledger.register_position(pos)

    leg = ledger.record_final(
        pos.ticket,
        1.0800,
        "TAKE_PROFIT",
    )

    assert leg.raw_r == 2.0
    assert leg.weighted_r == 2.0
    assert ledger.get(pos.ticket).net_r == 2.0


def test_half_partial_at_one_r_then_half_be_is_plus_half_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position(volume=1.0)
    ledger.register_position(pos)

    partial = ledger.record_partial(
        pos.ticket,
        volume=0.5,
        exit_price=1.1100,
    )

    assert partial.raw_r == 1.0
    assert partial.weighted_r == 0.5

    final = ledger.record_final(
        pos.ticket,
        exit_price=1.1000,
        kind="BREAKEVEN",
    )

    assert final.raw_r == 0.0
    assert final.weighted_r == 0.0

    record = ledger.get(pos.ticket)

    assert record.closed
    assert record.net_r == 0.5
    assert record.realized_volume == 1.0


def test_thirty_percent_at_one_r_then_rest_stop_is_minus_point_four_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position(volume=1.0)
    ledger.register_position(pos)

    ledger.record_partial(
        pos.ticket,
        volume=0.3,
        exit_price=1.1100,
    )

    ledger.record_final(
        pos.ticket,
        exit_price=1.0900,
        kind="STOP_LOSS",
    )

    record = ledger.get(pos.ticket)

    assert record.closed
    assert record.net_r == -0.4


def test_multiple_partials_are_volume_weighted():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position(volume=1.0)
    ledger.register_position(pos)

    ledger.record_partial(
        pos.ticket,
        volume=0.25,
        exit_price=1.1100,
    )

    ledger.record_partial(
        pos.ticket,
        volume=0.25,
        exit_price=1.1200,
    )

    ledger.record_final(
        pos.ticket,
        exit_price=1.1000,
        kind="BREAKEVEN",
    )

    # 25% at +1R = +0.25R
    # 25% at +2R = +0.50R
    # 50% at  0R =  0.00R
    assert ledger.get(pos.ticket).net_r == 0.75


def test_moved_stop_does_not_change_original_risk():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position(volume=1.0)

    record = ledger.register_position(pos)

    assert record.initial_risk == pytest.approx(
        0.0100
    )

    # Simulates BE/trailing after registration.
    pos.sl = 1.1050

    leg = ledger.record_final(
        pos.ticket,
        exit_price=1.1050,
        kind="TRAILING_STOP",
    )

    assert leg.raw_r == 0.5
    assert leg.weighted_r == 0.5


def test_cannot_exit_more_volume_than_remaining():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position(volume=1.0)
    ledger.register_position(pos)

    with pytest.raises(ValueError):
        ledger.record_partial(
            pos.ticket,
            volume=1.1,
            exit_price=1.1100,
        )


def test_closed_trade_cannot_receive_another_exit():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = make_buy_position()
    ledger.register_position(pos)

    ledger.record_final(
        pos.ticket,
        1.1200,
        "TAKE_PROFIT",
    )

    with pytest.raises(ValueError):
        ledger.record_partial(
            pos.ticket,
            0.1,
            1.1210,
        )


def test_summary_calculates_expectancy_and_profit_factor():
    ledger = RealizedTradeLedger(point=0.0001)

    trade1 = make_buy_position(ticket=1)
    trade2 = make_buy_position(ticket=2)
    trade3 = make_buy_position(ticket=3)

    ledger.register_position(trade1)
    ledger.register_position(trade2)
    ledger.register_position(trade3)

    ledger.record_final(
        1,
        1.1200,
        "TAKE_PROFIT",
    )  # +2R

    ledger.record_final(
        2,
        1.0900,
        "STOP_LOSS",
    )  # -1R

    ledger.record_final(
        3,
        1.1000,
        "BREAKEVEN",
    )  # 0R

    summary = ledger.summary()

    assert summary.trades == 3
    assert summary.wins == 1
    assert summary.losses == 1
    assert summary.breakeven == 1

    assert summary.gross_positive_r == 2.0
    assert summary.gross_negative_r == -1.0
    assert summary.net_r == 1.0

    assert summary.expectancy_r == pytest.approx(
        1.0 / 3.0,
        abs=1e-8,
    )

    assert summary.profit_factor_r == 2.0


def test_zero_risk_trade_is_not_given_fake_r():
    ledger = RealizedTradeLedger(point=0.0001)

    pos = Position(
        ticket=10,
        symbol="EURUSD",
        magic=7,
        type=PositionType.BUY,
        volume=1.0,
        price_open=1.1000,
        sl=0.0,
        tp=1.1200,
    )

    ledger.register_position(pos)

    leg = ledger.record_final(
        pos.ticket,
        1.1200,
        "TAKE_PROFIT",
    )

    assert leg.points == 200.0
    assert leg.raw_r is None
    assert leg.weighted_r is None

    summary = ledger.summary()

    # No invented normalized result.
    assert summary.trades == 0
    assert summary.net_r == 0.0