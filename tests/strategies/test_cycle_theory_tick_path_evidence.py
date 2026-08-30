from backend.strategies.cycle_theory.mt5_tick_path_evidence import (
    model_first_extreme,
    observed_first_extreme,
    summarize_tick_path_evidence,
    TickPathBarEvidence,
)


def test_model_first_extreme_matches_replay_contract():
    assert model_first_extreme(100.0, 101.0) == "LOW"
    assert model_first_extreme(100.0, 99.0) == "HIGH"
    assert model_first_extreme(100.0, 100.0) == "LOW"


def test_observed_first_extreme_uses_real_tick_order():
    ticks = [
        {"bid": 100.0},
        {"bid": 102.0},
        {"bid": 98.0},
    ]
    assert observed_first_extreme(ticks, high=102.0, low=98.0, tolerance=0.0) == "HIGH"


def test_observed_first_extreme_can_be_unresolved():
    ticks = [{"bid": 100.0}, {"bid": 101.0}]
    assert observed_first_extreme(ticks, high=102.0, low=98.0, tolerance=0.0) == "UNRESOLVED"


def test_summary_counts_matches_and_mismatches():
    items = [
        TickPathBarEvidence("a", "BULL", "LOW", "LOW", True, 10, 1.0, 2.0),
        TickPathBarEvidence("b", "BEAR", "HIGH", "LOW", False, 12, 1.0, 4.0),
        TickPathBarEvidence("c", "BULL", "LOW", "UNRESOLVED", None, 8, 1.0, 3.0),
    ]
    summary = summarize_tick_path_evidence(items)
    assert summary == {
        "bars": 3,
        "resolved": 2,
        "matches": 1,
        "mismatches": 1,
        "match_rate": 0.5,
        "total_ticks": 30,
    }


def test_module_has_no_order_send_path():
    import inspect
    import backend.strategies.cycle_theory.mt5_tick_path_evidence as module
    assert "order_send" not in inspect.getsource(module)
