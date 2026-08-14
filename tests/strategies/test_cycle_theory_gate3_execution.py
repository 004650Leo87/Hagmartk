from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.enums import (
    BotState,
    EntryMode,
    PositionType,
    TrailingMode,
)
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.persistence import CycleTheoryPersistence
from backend.strategies.cycle_theory.state_machine import CycleTheoryStateMachine
from backend.strategies.cycle_theory.execution_model import CycleTheoryExecutionModel
from backend.strategies.cycle_theory.position_manager import CycleTheoryPositionManager
from backend.strategies.cycle_theory.research_adapter import CycleTheoryResearchAdapter


def make_execution(entry_mode):
    inputs = baseline_inputs()
    inputs.entry_mode = entry_mode

    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002
    broker.spread_pts = 2

    persistence = CycleTheoryPersistence()
    sm = CycleTheoryStateMachine(
        "EURUSD",
        inputs.magic_num,
        broker,
    )
    sm.state.is_system_on = True

    execution = CycleTheoryExecutionModel(
        broker,
        inputs,
        persistence,
    )

    return inputs, broker, sm, execution


def test_market_buy_opens_immediately_at_ask():
    inputs, broker, sm, execution = make_execution(
        EntryMode.ENTRY_MARKET
    )

    ok = execution.executar_compra(
        sm,
        sl=1.0950,
        ep=1.0990,
        dist_sl=0.0050,
    )

    assert ok is True
    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 1

    pos = broker.positions[0]

    assert pos.type is PositionType.BUY
    assert pos.price_open == broker.ask
    assert pos.sl == 1.0950
    assert sm.state.current_state is BotState.STATE_TRADING


def test_buy_limit_waits_then_fill_preserves_volume_and_price():
    inputs, broker, sm, execution = make_execution(
        EntryMode.ENTRY_PULLBACK_25
    )

    ok = execution.executar_compra(
        sm,
        sl=1.0950,
        ep=1.0990,
        dist_sl=0.0040,
    )

    assert ok is True
    assert len(broker.positions) == 0
    assert len(broker.pending_orders) == 1

    order = broker.pending_orders[0]
    submitted_volume = order.volume
    submitted_price = order.price_open

    position_ticket = broker.fill_pending(order.ticket)

    assert position_ticket is not None
    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 1

    pos = broker.positions[0]

    assert pos.volume == submitted_volume
    assert pos.price_open == submitted_price
    assert pos.sl == 1.0950


def test_sell_limit_waits_then_fill_preserves_volume_and_price():
    inputs, broker, sm, execution = make_execution(
        EntryMode.ENTRY_PULLBACK_50
    )

    ok = execution.executar_venda(
        sm,
        sl=1.1050,
        ep=1.1010,
        dist_sl=0.0040,
    )

    assert ok is True
    assert len(broker.positions) == 0
    assert len(broker.pending_orders) == 1

    order = broker.pending_orders[0]
    submitted_volume = order.volume
    submitted_price = order.price_open

    position_ticket = broker.fill_pending(order.ticket)

    assert position_ticket is not None
    assert len(broker.pending_orders) == 0
    assert len(broker.positions) == 1

    pos = broker.positions[0]

    assert pos.volume == submitted_volume
    assert pos.price_open == submitted_price
    assert pos.type is PositionType.SELL
    assert pos.sl == 1.1050


def test_pullback_missed_cancels_pending_and_resets_cycle():
    inputs = baseline_inputs()
    inputs.entry_mode = EntryMode.ENTRY_PULLBACK_25

    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002

    adapter = CycleTheoryResearchAdapter(
        "EURUSD",
        inputs,
        broker,
    )

    adapter.sm.state.is_system_on = True
    adapter.sm.state.current_state = BotState.STATE_TRADING
    adapter.sm.state.super_size = 0.0100

    ticket = broker.buy_limit(
        0.20,
        1.1000,
        1.0900,
        0.0,
        inputs.magic_num,
    )

    assert ticket is not None
    assert len(broker.pending_orders) == 1

    broker.bid = 1.1100

    adapter.check_pending_cancellation()

    assert len(broker.pending_orders) == 0
    assert adapter.sm.state.current_state is BotState.STATE_STARTING
    assert adapter.sm.state.setup_dir == 0
    assert adapter.sm.state.dash_status == "PULLBACK PERDIDO → NOVO CICLO"


def test_partial_level_one_reduces_position_volume():
    inputs = baseline_inputs()
    inputs.use_partial = True
    inputs.partial_pct = 50.0

    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002

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

    ticket = broker.buy(
        0.20,
        1.0900,
        0.0,
        inputs.magic_num,
    )

    assert ticket is not None

    sm.state.super_size = 0.0100

    broker.bid = 1.1102

    closed = manager.manage_partials(sm)

    assert closed is False
    assert len(broker.positions) == 1
    assert broker.positions[0].volume == 0.10
    assert sm.state.last_partial_level == 1


def test_breakeven_runs_even_when_trailing_is_off():
    inputs = baseline_inputs()
    inputs.use_breakeven = True
    inputs.be_activation = 10
    inputs.trailing_mode = TrailingMode.TRAIL_OFF

    broker = MockBroker("EURUSD")
    broker.bid = 1.1000
    broker.ask = 1.1002

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

    ticket = broker.buy(
        0.20,
        1.0950,
        0.0,
        inputs.magic_num,
    )

    assert ticket is not None

    pos = broker.positions[0]
    open_price = pos.price_open

    broker.bid = open_price + (20 * broker.point)

    manager.manage_trailing(sm)

    assert sm.state.be_applied is True
    assert pos.sl == round(
        open_price + (10 * broker.point),
        broker.digits,
    )
