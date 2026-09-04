import json

import pandas as pd

from backend.services.fibonacci_prospective_telemetry import (
    FibonacciProspectiveTelemetryEngine,
    _target_outcomes,
)
from backend.services.shadow_store import ShadowStoreRepository


def base_record():
    return {
        "telemetry_id": "fibtele_test_1",
        "research_scope": "HDF_FIBONACCI_RESEARCH_V1",
        "candidate_id": "hdf_dvp_exit_2r",
        "occurrence_id": "occ_1",
        "symbol": "EURUSD",
        "timeframe": "H1",
        "direction": "BULLISH",
        "mode": "PRE_REVERSAL_STRICT_V1",
        "role": "CONFLUENCE",
        "policy_id": "POLICY_V1",
        "decision_time": "2026-09-03T20:00:00+00:00",
        "decision_status": "PASS",
        "decision_reason": "FROZEN",
        "anchor_a_time": "a",
        "anchor_a_price": 1.0,
        "anchor_a_confirmed_at": "a_confirmed",
        "anchor_b_time": "b",
        "anchor_b_price": 2.0,
        "anchor_b_confirmed_at": "b_confirmed",
        "levels_json": json.dumps({"2.0": 3.0}),
        "matched_levels_json": json.dumps([2.0]),
        "activated": 0,
        "activation_level": 2.0,
        "entry_time": "",
        "entry_price": 0.0,
        "stop_price": 1.0,
        "target_outcomes_json": "{}",
        "last_observed_candle": "2026-09-03T20:00:00+00:00",
        "source": "TEST",
        "is_test": 1,
        "created_at": "2026-09-03T20:00:01+00:00",
        "updated_at": "2026-09-03T20:00:01+00:00",
    }


def test_store_upsert_preserves_decision_snapshot(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "shadow.db"))
    first = base_record()
    store.upsert_fibonacci_telemetry(first)

    later = dict(first)
    later["decision_status"] = "FAIL"
    later["anchor_a_price"] = 99.0
    later["levels_json"] = json.dumps({"2.0": 999.0})
    later["activated"] = 1
    later["entry_time"] = "2026-09-03T21:00:00+00:00"
    later["entry_price"] = 2.1
    later["target_outcomes_json"] = json.dumps({"2.0": {"state": "TARGET_FIRST"}})
    later["updated_at"] = "2026-09-03T21:05:00+00:00"
    store.upsert_fibonacci_telemetry(later)

    rows = store.get_fibonacci_telemetry(source="TEST", is_test=True)
    assert len(rows) == 1
    row = rows[0]
    assert row["decision_status"] == "PASS"
    assert row["anchor_a_price"] == 1.0
    assert json.loads(row["levels_json"])["2.0"] == 3.0
    assert row["activated"] == 1
    assert row["entry_price"] == 2.1
    assert json.loads(row["target_outcomes_json"])["2.0"]["state"] == "TARGET_FIRST"


def test_target_outcome_is_conservative_on_same_bar():
    df = pd.DataFrame([
        {"high": 105.0, "low": 95.0},
    ])
    out = _target_outcomes(df, 0, "BULLISH", 100.0, 96.0, {1.0: 104.0})
    assert out["1.0"]["state"] == "AMBIGUOUS_SAME_BAR"


def test_t0_boundary_rejects_historical_live_rows():
    assert FibonacciProspectiveTelemetryEngine._is_prospective(
        "2026-09-03T20:00:00+00:00",
        "2026-09-03T20:00:01+00:00",
        False,
    ) is False
    assert FibonacciProspectiveTelemetryEngine._is_prospective(
        "2026-09-03T20:00:01+00:00",
        "2026-09-03T20:00:01+00:00",
        False,
    ) is True
    assert FibonacciProspectiveTelemetryEngine._is_prospective("old", "new", True) is True


def test_feature_t0_is_stricter_than_existing_shadow_t0(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "shadow_t0.db"))
    engine = FibonacciProspectiveTelemetryEngine(
        store=store,
        started_at="2026-09-03T20:05:00+00:00",
    )
    assert engine._effective_started_at("2026-09-03T20:00:00+00:00") == "2026-09-03T20:05:00+00:00"
    assert engine._effective_started_at("2026-09-03T21:00:00+00:00") == "2026-09-03T21:00:00+00:00"


def test_telemetry_id_separates_live_and_test_sources():
    from backend.services.fibonacci_prospective_telemetry import _telemetry_id

    args = ("EURUSD", "H1", "BULLISH", "2026-09-03T20:00:00+00:00", "PRE_REVERSAL_STRICT_V1")
    assert _telemetry_id(*args, "LIVE_PROSPECTIVE") != _telemetry_id(*args, "TEST")
