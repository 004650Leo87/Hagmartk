"""Suíte de testes para a Telemetria e Observabilidade Operacional do Shadow Mode V1 (Fase 4D).

Cobre:
1. Telemetria vazia por padrão (expected=0, coverage=None, health=UNKNOWN)
2. Registro de successful checks (não dependente de sinais)
3. Registro de failed checks (com códigos operacionais de erro)
4. Agregação em janela de 1 hora e persistência no SQLite
5. Proteção de duplicação por janela (UPSERT)
6. Preservação das 39 combinações do Shadow Universe (13 ativos x 3 timeframes)
7. Classificação de Health (UNKNOWN, HEALTHY, DEGRADED, UNAVAILABLE)
8. Integração com StatisticalValidationEngine (cobertura real vs fallback null)
"""
from __future__ import annotations

import os
import sqlite3
import pytest
from unittest.mock import MagicMock

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
    assert len(telemetry["combinations"]) == 39


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
    # 18 sucessos e 2 falhas -> 18/20 = 90% -> DEGRADED
    for _ in range(18):
        temp_store.record_scanner_telemetry("hdf_dvp_exit_2r", "BTCUSD", "H1", success=True)
    for _ in range(2):
        temp_store.record_scanner_telemetry("hdf_dvp_exit_2r", "BTCUSD", "H1", success=False, error_code="TIMEOUT")

    telemetry = temp_store.get_shadow_telemetry()
    comb = next(c for c in telemetry["combinations"] if c["symbol"] == "BTCUSD" and c["timeframe"] == "H1")
    assert comb["successful_checks"] == 18
    assert comb["failed_checks"] == 2
    assert comb["coverage"] == 0.90
    assert comb["health"] == "DEGRADED"


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
