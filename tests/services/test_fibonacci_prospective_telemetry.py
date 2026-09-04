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


def test_research_summary_is_read_only_and_insufficient_when_empty(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "summary_empty.db"))
    engine = FibonacciProspectiveTelemetryEngine(store=store)
    summary = engine.build_research_summary()

    assert summary["research_state"] == "RESEARCH_ONLY"
    assert summary["promotion_allowed"] is False
    assert summary["total_records"] == 0
    assert summary["modes"]["PRE_REVERSAL_STRICT_V1"]["sample_class"] == "INSUFFICIENT"
    assert summary["modes"]["POST_REVERSAL_PATTERN_RANGE_V1"]["sample_class"] == "INSUFFICIENT"
    assert "NO_AUTOMATIC_PROMOTION" in summary["reason_codes"]


def test_research_summary_reuses_central_sample_thresholds(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "summary_thresholds.db"))
    engine = FibonacciProspectiveTelemetryEngine(store=store)

    for i in range(20):
        decision_time = f"2026-09-03T20:{i:02d}:00+00:00"
        pre = base_record()
        pre.update({"telemetry_id": f"pre_{i}", "occurrence_id": f"occ_{i}", "decision_time": decision_time})
        store.upsert_fibonacci_telemetry(pre)
        post = base_record()
        post.update({
            "telemetry_id": f"post_{i}",
            "occurrence_id": f"occ_{i}",
            "decision_time": decision_time,
            "mode": "POST_REVERSAL_PATTERN_RANGE_V1",
            "role": "TARGET",
            "decision_status": "AVAILABLE",
            "activated": 1,
            "target_outcomes_json": json.dumps({
                "1.0": {"state": "TARGET_FIRST", "bars": 2, "price": 3.0},
                "2.0": {"state": "STOP_FIRST", "bars": 5, "price": 4.0},
            }),
        })
        store.upsert_fibonacci_telemetry(post)

    summary = engine.build_research_summary(source="TEST", is_test=True)
    assert summary["promotion_allowed"] is False
    assert summary["sample_thresholds"] == {"INSUFFICIENT": 20, "EARLY": 50, "USABLE": 100}
    assert summary["modes"]["PRE_REVERSAL_STRICT_V1"]["maturity_count"] == 20
    assert summary["modes"]["PRE_REVERSAL_STRICT_V1"]["sample_class"] == "EARLY"
    assert summary["modes"]["POST_REVERSAL_PATTERN_RANGE_V1"]["resolved_events"] == 20
    assert summary["modes"]["POST_REVERSAL_PATTERN_RANGE_V1"]["sample_class"] == "EARLY"
    assert summary["modes"]["POST_REVERSAL_PATTERN_RANGE_V1"]["target_level_states"]["1.0"]["TARGET_FIRST"] == 20
