"""Gate 3H: broker-margin fidelity for Cycle Theory V111."""
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.execution_model import CycleTheoryExecutionModel
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.persistence import CycleTheoryPersistence


def _model(broker):
    return CycleTheoryExecutionModel(broker, baseline_inputs(), CycleTheoryPersistence())


def test_missing_broker_margin_contract_does_not_invent_fixed_rate():
    broker = MockBroker("EURUSD")
    assert broker.order_calc_margin_buy(1.0) is None


def test_calc_lot_uses_explicit_broker_margin_result_when_available():
    broker = MockBroker("EURUSD")
    broker.margin_free = 500.0
    broker.margin_calculator = lambda lot, price: lot * 2000.0
    model = _model(broker)

    # baseline auto-balance => 2.00 lots at 100k / 500 * 0.01.
    # Required margin = 4000, free = 500 -> scales to 0.25.
    assert model.calc_lot(1.0) == 0.25
