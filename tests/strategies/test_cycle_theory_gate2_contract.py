"""Cycle Theory V111 — Gate 2 contract locks.

Congela propriedades críticas da baseline fidelity antes dos testes
de execução e da futura pesquisa de parâmetros.
"""

from backend.strategies.cycle_theory.enums import (
    EntryMode,
    LotMode,
    TrailingMode,
    TriggerMode,
)
from backend.strategies.cycle_theory.inputs import (
    BE_PROTECT_PTS,
    LICENSE_ACCOUNT_1,
    LICENSE_ACCOUNT_2,
    LICENSE_LIMIT,
    TOTAL_CONSTANTS,
    TOTAL_INPUTS,
    baseline_inputs,
)
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.execution_model import (
    CycleTheoryExecutionModel,
    get_smart_buffer,
)
from backend.strategies.cycle_theory.persistence import CycleTheoryPersistence


def test_v111_exact_input_contract():
    i = baseline_inputs()

    assert i.field_count() == TOTAL_INPUTS == 30
    assert TOTAL_CONSTANTS == 4

    assert i.lot_mode is LotMode.LOT_AUTO_BALANCE
    assert i.fixed_lot == 0.01
    assert i.balance_step == 500.0
    assert i.magic_num == 1

    assert i.use_partial is True
    assert i.partial_pct == 50.0

    assert i.max_daily_loss == 0.0
    assert i.max_daily_profit == 0.0
    assert i.max_daily_trades == 0

    assert i.max_spread == 30

    assert i.use_capital_trail is True
    assert i.capital_goal == 50.0
    assert i.capital_protect == 25.0

    assert i.split_channel_points == 1000

    assert i.start_time == "01:00"
    assert i.end_entry_time == "23:00"
    assert i.close_all_time == "23:50"

    assert i.trigger_mode is TriggerMode.GATILHO_EXPANSAO
    assert i.fixed_tf == "PERIOD_CURRENT"

    assert i.entry_mode is EntryMode.ENTRY_PULLBACK_25

    assert i.max_channel_size == 3000
    assert i.stop_buffer == 20
    assert i.expansion_levels == 3

    assert i.use_breakeven is False
    assert i.be_activation == 500

    assert i.send_push is False
    assert i.deviation == 100

    assert i.trailing_mode is TrailingMode.TRAIL_ATR
    assert i.atr_period == 14
    assert i.atr_multiplier == 1.5


def test_v111_internal_constants_contract():
    assert LICENSE_ACCOUNT_1 == 0
    assert LICENSE_ACCOUNT_2 == 0
    assert str(LICENSE_LIMIT) == "2050-12-31"
    assert BE_PROTECT_PTS == 10


def test_obs04_calc_lot_ignores_stop_distance():
    i = baseline_inputs()
    broker = MockBroker("EURUSD")
    execution = CycleTheoryExecutionModel(
        broker,
        i,
        CycleTheoryPersistence(),
    )

    assert execution.calc_lot(0.0001) == execution.calc_lot(1000.0)


def test_zero_stop_buffer_falls_back_to_50_points():
    i = baseline_inputs()
    i.stop_buffer = 0

    assert get_smart_buffer(i) == 50


def test_pullback_zero_remains_limit_contract():
    assert EntryMode.ENTRY_PULLBACK_0 is not EntryMode.ENTRY_MARKET
