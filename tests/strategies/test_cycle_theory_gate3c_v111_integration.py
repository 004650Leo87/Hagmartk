import pytest

from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.accounting_broker import (
    AccountingBrokerBridge,
)
from backend.strategies.cycle_theory.realized_ledger import (
    RealizedTradeLedger,
)
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.persistence import (
    CycleTheoryPersistence,
)
from backend.strategies.cycle_theory.state_machine import (
    CycleTheoryStateMachine,
)
from backend.strategies.cycle_theory.position_manager import (
    CycleTheoryPositionManager,
)
from backend.strategies.cycle_theory.enums import TrailingMode


def make_stack():
    inputs = baseline_inputs()

    raw_broker = MockBroker("EURUSD")
    raw_broker.bid = 1.1000
    raw_broker.ask = 1.1002

    ledger = RealizedTradeLedger(
        point=raw_broker.point
    )

    broker = AccountingBrokerBridge(
        broker=raw_broker,
        ledger=ledger,
    )

    persistence = CycleTheoryPersistence()

    sm = CycleTheoryStateMachine(
        "EURUSD",
        inputs.magic_num,
        broker,
    )

    manager = CycleTheoryPositionManager(
        broker,
        inputs,
        persistence,
    )

    return (
        inputs,
        raw_broker,
        broker,
        ledger,
        sm,
        manager,
    )


def test_v111_partial_then_breakeven_then_final_close_is_consolidated():
    (
        inputs,
        raw_broker,
        broker,
        ledger,
        sm,
        manager,
    ) = make_stack()

    inputs.use_partial = True
    inputs.partial_pct = 50.0

    inputs.use_breakeven = True
    inputs.be_activation = 20

    inputs.trailing_mode = TrailingMode.TRAIL_OFF

    ticket = broker.buy(
        1.0,
        1.0902,
        0.0,
        inputs.magic_num,
    )

    assert ticket is not None

    pos = raw_broker.positions[0]

    entry = pos.price_open

    # Original risk:
    # entry 1.1002 -> SL 1.0902 = 0.0100
    assert ledger.get(ticket).initial_risk == pytest.approx(
        0.0100
    )

    # V111 partial level 1 at +super_size.
    sm.state.super_size = 0.0100

    raw_broker.bid = entry + 0.0100
    raw_broker.ask = raw_broker.bid + 0.0002

    closed = manager.manage_partials(sm)

    assert closed is False
    assert raw_broker.positions[0].volume == pytest.approx(
        0.5
    )

    record = ledger.get(ticket)

    assert len(record.legs) == 1
    assert record.legs[0].kind == "PARTIAL"
    assert record.legs[0].raw_r == pytest.approx(
        1.0
    )
    assert record.legs[0].weighted_r == pytest.approx(
        0.5
    )

    # Breakeven is applied by the actual V111 manager.
    manager.manage_trailing(sm)

    assert sm.state.be_applied is True

    moved_sl = raw_broker.positions[0].sl

    assert moved_sl > entry

    # Market returns to the V111 breakeven-protected stop.
    raw_broker.bid = moved_sl
    raw_broker.ask = moved_sl + 0.0002

    assert broker.position_close(ticket)

    record = ledger.get(ticket)

    assert record.closed
    assert record.remaining_volume == 0.0
    assert len(record.legs) == 2

    final_leg = record.legs[-1]

    assert final_leg.kind == "FINAL_CLOSE"

    # Critical contract:
    # moved stop MUST NOT replace original risk denominator.
    expected_final_raw_r = (
        moved_sl - entry
    ) / 0.0100

    assert final_leg.raw_r == pytest.approx(
        expected_final_raw_r
    )

    expected_net_r = (
        0.5
        + expected_final_raw_r * 0.5
    )

    assert record.net_r == pytest.approx(
        expected_net_r
    )


def test_v111_partial_ledger_summary_counts_one_completed_trade():
    (
        inputs,
        raw_broker,
        broker,
        ledger,
        sm,
        manager,
    ) = make_stack()

    inputs.use_partial = True
    inputs.partial_pct = 50.0

    ticket = broker.buy(
        1.0,
        1.0902,
        0.0,
        inputs.magic_num,
    )

    assert ticket is not None

    pos = raw_broker.positions[0]
    entry = pos.price_open

    sm.state.super_size = 0.0100

    raw_broker.bid = entry + 0.0100
    raw_broker.ask = raw_broker.bid + 0.0002

    manager.manage_partials(sm)

    # Remaining half exits at original stop.
    raw_broker.bid = 1.0902
    raw_broker.ask = 1.0904

    assert broker.position_close(ticket)

    record = ledger.get(ticket)

    # +0.50R partial, then -0.50R remainder.
    assert record.net_r == pytest.approx(0.0)

    summary = ledger.summary()

    assert summary.trades == 1
    assert summary.wins == 0
    assert summary.losses == 0
    assert summary.breakeven == 1
    assert summary.net_r == pytest.approx(0.0)