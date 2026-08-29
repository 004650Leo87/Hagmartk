"""Gate 3I: explicit economic assumptions for research replay."""
from backend.strategies.cycle_theory.broker import MockBroker
from backend.strategies.cycle_theory.historical_replay import CycleTheoryHistoricalReplay
from backend.strategies.cycle_theory.inputs import baseline_inputs


def test_replay_declares_zero_cost_model():
    replay = CycleTheoryHistoricalReplay(
        "EURUSD", "M5", baseline_inputs(), MockBroker("EURUSD")
    )
    assert replay.cost_model == "ZERO_COMMISSION_ZERO_SWAP"


def test_replay_declares_idealized_gap_slippage_model():
    replay = CycleTheoryHistoricalReplay(
        "EURUSD", "M5", baseline_inputs(), MockBroker("EURUSD")
    )
    assert replay.fill_model == "OHLC_PATH_IDEALIZED_NO_SLIPPAGE"
