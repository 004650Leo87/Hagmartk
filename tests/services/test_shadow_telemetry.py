"""Suíte de testes para a Telemetria e Observabilidade Operacional do Shadow Mode V1 (Fase 4D).

Cobre:
1. Telemetria vazia por padrão (expected=0, coverage=None, health=UNKNOWN)
2. Registro de successful checks (não dependente de sinais)
3. Registro de failed checks (com códigos operacionais de erro)
4. Agregação em janela de 1 hora e persistência no SQLite
5. Proteção de duplicação por janela (UPSERT)
6. Preservação das 39 combinações do Shadow Universe (13 ativos x 8 timeframes)
7. Classificação de Health (UNKNOWN, HEALTHY, DEGRADED, UNAVAILABLE)
8. Integração com StatisticalValidationEngine (cobertura real vs fallback null)
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from backend.domain.shadow_models import ShadowScannerState
from backend.services.shadow_store import ShadowStoreRepository
from backend.services.shadow_statistical_validation import ShadowStatisticalValidationEngine


@pytest.fixture
def temp_store(tmp_path):
    db_file = str(tmp_path / "test_shadow_telemetry.db")
    return ShadowStoreRepository(db_path=db_file)


def test_telemetry_starts_empty(temp_store):
    telemetry = temp_store.get_shadow_telemetry()
    assert telemetry["global"]["expected_checks"] == 0
    assert telemetry["global"]["successful_checks"] == 0
    assert telemetry["global"]["failed_checks"] == 0
    assert telemetry["global"]["coverage"] is None
    assert telemetry["global"]["health"] == "UNKNOWN"
    assert len(telemetry["combinations"]) == 104


def test_successful_check_recording(temp_store):
    temp_store.record_scanner_telemetry("hdf_dvp_exit_2r", "EURUSD", "H1", success=True)
    telemetry = temp_store.get_shadow_telemetry()

    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "H1")
    assert comb["successful_checks"] == 1
    assert comb["failed_checks"] == 0
    assert comb["expected_checks"] >= 1
    assert comb["coverage"] == 1.0
    assert comb["health"] == "HEALTHY"


def test_failed_check_recording(temp_store):
    temp_store.record_scanner_telemetry("hdf_dvp_exit_2r", "GBPUSD", "M15", success=False, error_code="MT5_UNAVAILABLE")
    telemetry = temp_store.get_shadow_telemetry()

    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "GBPUSD" and c["timeframe"] == "M15")
    assert comb["successful_checks"] == 0
    assert comb["failed_checks"] == 1
    assert comb["health"] == "UNAVAILABLE"


def test_degraded_health_classification(temp_store):
    # 18 hourly slots successful and 2 hourly slots failed -> 18/20 = 90% -> DEGRADED
    for hour in range(18):
        temp_store.record_scanner_telemetry(
            "hdf_dvp_exit_2r", "BTCUSD", "H1", success=True,
            now_str=f"2026-09-03T{hour:02d}:05:00+00:00",
        )
    for hour in range(18, 20):
        temp_store.record_scanner_telemetry(
            "hdf_dvp_exit_2r", "BTCUSD", "H1", success=False, error_code="TIMEOUT",
            now_str=f"2026-09-03T{hour:02d}:05:00+00:00",
        )

    telemetry = temp_store.get_shadow_telemetry()
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "BTCUSD" and c["timeframe"] == "H1")
    assert comb["successful_checks"] == 18
    assert comb["failed_checks"] == 2
    assert comb["coverage"] == 0.90
    assert comb["health"] == "DEGRADED"



def test_repeated_failure_same_slot_is_idempotent(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T10:10:00+00:00", True)
    for second in (1, 4, 7, 10):
        temp_store.record_scanner_telemetry(
            candidate, "EURUSD", "M15", success=False, error_code="MARKET_DATA_UNAVAILABLE",
            now_str=f"2026-09-04T10:15:{second:02d}+00:00",
        )
    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 1
    assert comb["failed_checks"] == 1


def test_success_replaces_failure_in_same_slot(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.record_scanner_telemetry(
        candidate, "EURUSD", "H1", success=False, error_code="MARKET_DATA_UNAVAILABLE",
        now_str="2026-09-04T10:05:00+00:00",
    )
    temp_store.record_scanner_telemetry(
        candidate, "EURUSD", "H1", success=True, now_str="2026-09-04T10:06:00+00:00",
    )
    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "H1")
    assert comb["expected_checks"] == 1
    assert comb["successful_checks"] == 1
    assert comb["failed_checks"] == 0
    assert comb["coverage"] == 1.0

def test_statistical_engine_consumes_real_telemetry(temp_store):
    # Sem telemetria: scanner_coverage é None
    mock_perf = MagicMock()
    mock_perf.store = temp_store
    mock_perf.build_snapshot.return_value = MagicMock(same_bar_ambiguous_count=0, data_quality_warnings=[])

    stat_engine = ShadowStatisticalValidationEngine(perf_engine=mock_perf)
    snap1 = stat_engine.build_validation_snapshot()
    assert snap1.measurement["scanner_coverage"] is None

    # Com telemetria real (100% de sucesso): scanner_coverage é 1.0 e quality_state é DATA_QUALITY_OK
    for _ in range(5):
        temp_store.record_scanner_telemetry("hdf_dvp_exit_2r", "EURUSD", "H1", success=True)

    snap2 = stat_engine.build_validation_snapshot()
    assert snap2.measurement["scanner_coverage"] == 1.0
    assert snap2.operational_policy["quality_state"] == "DATA_QUALITY_OK"


def test_m15_expected_checks_follow_elapsed_boundaries(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.record_scanner_telemetry(candidate, "EURUSD", "M15", success=True, now_str="2026-09-04T10:00:02+00:00")
    temp_store.record_scanner_telemetry(candidate, "EURUSD", "M15", success=True, now_str="2026-09-04T10:15:02+00:00")
    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 2
    assert comb["successful_checks"] == 2
    assert comb["coverage"] == 1.0


def test_m15_expected_checks_respect_mid_hour_shadow_t0(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T10:40:00+00:00", True)
    temp_store.record_scanner_telemetry(candidate, "GBPUSD", "M15", success=True, now_str="2026-09-04T10:45:02+00:00")
    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "GBPUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 1
    assert comb["successful_checks"] == 1
    assert comb["coverage"] == 1.0


def test_m15_expected_checks_accept_production_naive_utc_timestamp(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04 10:40:00", True)
    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "M15", success=True, now_str="2026-09-04 10:45:02"
    )
    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 1
    assert comb["successful_checks"] == 1
    assert comb["coverage"] == 1.0


def test_telemetry_t0_excludes_pre_reset_m15_slots(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T10:00:00+00:00", True)
    temp_store.save_telemetry_session(candidate, "2026-09-04T10:40:00+00:00")
    temp_store.record_scanner_telemetry(
        candidate, "EURUSD", "M15", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T10:41:00+00:00",
    )
    before = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in before["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 0
    assert comb["failed_checks"] == 0

    temp_store.record_scanner_telemetry(
        candidate, "EURUSD", "M15", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T10:45:01+00:00",
    )
    after = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in after["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 1
    assert comb["failed_checks"] == 1


def test_h1_and_h4_expected_slots_follow_real_boundaries(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_telemetry_session(candidate, "2026-09-04T10:10:00+00:00")

    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "H1", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T10:20:00+00:00",
    )
    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "H4", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T10:20:00+00:00",
    )
    telemetry = temp_store.get_shadow_telemetry(candidate)
    h1 = next(c for c in telemetry["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H1")
    h4 = next(c for c in telemetry["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H4")
    assert h1["expected_checks"] == 0
    assert h4["expected_checks"] == 0

    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "H1", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T11:00:01+00:00",
    )
    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "H4", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T12:00:01+00:00",
    )
    telemetry = temp_store.get_shadow_telemetry(candidate)
    h1 = next(c for c in telemetry["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H1")
    h4 = next(c for c in telemetry["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H4")
    assert h1["expected_checks"] == 1
    assert h1["failed_checks"] == 1
    assert h4["expected_checks"] == 1
    assert h4["failed_checks"] == 1


def test_missing_telemetry_row_still_counts_expected_slot(temp_store, monkeypatch):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T10:00:00+00:00", True)
    temp_store.save_telemetry_session(candidate, "2026-09-04T10:10:00+00:00")
    temp_store.save_scanner_state(ShadowScannerState(
        candidate_id=candidate, symbol="EURUSD", timeframe="M15",
        last_processed_candle="2026-09-04T10:00:00+00:00",
    ))
    monkeypatch.setattr(
        "backend.core.time_utils.now_utc_datetime",
        lambda: datetime(2026, 9, 4, 10, 16, tzinfo=timezone.utc),
    )

    telemetry = temp_store.get_shadow_telemetry(candidate)
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "EURUSD" and c["timeframe"] == "M15")
    assert comb["expected_checks"] == 1
    assert comb["successful_checks"] == 0
    assert comb["coverage"] == 0.0
    assert comb["health"] == "UNAVAILABLE"


def test_h4_expected_denominator_respects_observed_broker_phase(temp_store, monkeypatch):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T01:40:49+00:00", True)
    temp_store.save_telemetry_session(candidate, "2026-09-04T11:56:21+00:00")
    temp_store.save_scanner_state(ShadowScannerState(
        candidate_id=candidate, symbol="USDJPY", timeframe="H4",
        last_processed_candle="2026-09-04T05:00:00+00:00",
    ))
    monkeypatch.setattr(
        "backend.core.time_utils.now_utc_datetime",
        lambda: datetime(2026, 9, 4, 12, 5, tzinfo=timezone.utc),
    )
    before = temp_store.get_shadow_telemetry(candidate)
    h4 = next(c for c in before["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H4")
    assert h4["expected_checks"] == 0

    monkeypatch.setattr(
        "backend.core.time_utils.now_utc_datetime",
        lambda: datetime(2026, 9, 4, 13, 1, tzinfo=timezone.utc),
    )
    after = temp_store.get_shadow_telemetry(candidate)
    h4 = next(c for c in after["combinations"] if c["symbol"] == "USDJPY" and c["timeframe"] == "H4")
    assert h4["expected_checks"] == 1
    assert h4["coverage"] == 0.0


def test_h4_failure_is_recorded_on_observed_broker_phase(temp_store):
    candidate = "hdf_dvp_exit_2r"
    temp_store.save_shadow_session(candidate, "2026-09-04T01:40:49+00:00", True)
    temp_store.save_telemetry_session(candidate, "2026-09-04T11:56:21+00:00")
    temp_store.save_scanner_state(ShadowScannerState(
        candidate_id=candidate, symbol="USDJPY", timeframe="H4",
        last_processed_candle="2026-09-04T05:00:00+00:00",
    ))

    temp_store.record_scanner_telemetry(
        candidate, "USDJPY", "H4", success=False,
        error_code="MARKET_DATA_UNAVAILABLE", now_str="2026-09-04T13:00:01+00:00",
    )
    with temp_store._get_connection() as conn:
        row = conn.execute(
            "SELECT expected_checks, successful_checks, failed_checks FROM shadow_scanner_telemetry WHERE candidate_id=? AND symbol=? AND timeframe=?",
            (candidate, "USDJPY", "H4"),
        ).fetchone()
    assert tuple(row) == (1, 0, 1)
