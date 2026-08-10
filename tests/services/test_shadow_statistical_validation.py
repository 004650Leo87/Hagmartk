"""Suíte de testes para o Hagmartk Statistical Validation Engine V1 Hardened (Fase 4C-B.1).

Cobre:
1. Validação independente de quantis t-Student (df = 1, 2, 5, 10, 20, 30, 50, 100, 120, 200) com tolerância 10^-4
2. Validação rigorosa do parâmetro confidence (rejeição de != 0.95)
3. Amostras conhecidas de Expectancy CI (n=2, amostra pequena mista, amostra maior)
4. Manutenção de n=0, n=1 e zero variance
5. Semântica honesta de Scanner Coverage (scanner_coverage = None quando sem telemetria histórica)
6. Presença obrigaória de SCANNER_COVERAGE_UNAVAILABLE nos warnings e reason_codes
7. Imperativo: requires_human_review SEMPRE True
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.domain.shadow_models import ShadowEvent
from backend.services.shadow_statistical_validation import (
    ShadowStatisticalValidationEngine,
    classify_historical_compatibility,
    classify_operational_maturity,
    classify_statistical_evidence,
    classify_statistical_precision,
    compute_t_student_expectancy_interval,
    compute_wilson_score_interval,
    get_t_critical_value,
)


@pytest.fixture
def mock_perf_engine():
    perf = MagicMock()
    perf.store.list_history_events.return_value = []
    perf.store.get_shadow_telemetry.return_value = {
        "global": {"expected_checks": 0, "successful_checks": 0, "failed_checks": 0, "coverage": None, "health": "UNKNOWN"},
        "combinations": []
    }

    snap = MagicMock()
    snap.total_r = 0.0
    snap.max_drawdown_r = 0.0
    snap.same_bar_ambiguous_count = 0
    snap.data_quality_warnings = []
    perf.build_snapshot.return_value = snap

    return perf


def make_terminal_event(
    event_id: str,
    state: str,
    time_str: str = "2026-08-10 14:00:00",
) -> ShadowEvent:
    return ShadowEvent(
        event_id=event_id,
        candidate_id="hdf_dvp_exit_2r",
        candidate_version="1.0.0",
        symbol="EURUSD",
        asset_class="FOREX",
        timeframe="H1",
        direction="BULLISH",
        confluence_time=time_str,
        current_state=state,
        activated_at="2026-08-10 13:00:00",
        updated_at=time_str,
        entry_price=1.1000,
        initial_stop=1.0950,
        target_2R=1.1100,
        initial_risk=0.0050,
        metadata={"synthetic": False, "bootstrap_detected": False},
        created_at=time_str,
    )


# ============================================================
# 1. PARTE D — Validação Independente do t-Student
# ============================================================

def test_t_critical_value_independent_references():
    """Valida quantis t-Student contra constantes estatísticas conhecidas (tolerância 10^-4)."""
    ref_table = {
        1: 12.7062,
        2: 4.3027,
        5: 2.5706,
        10: 2.2281,
        20: 2.0860,
        30: 2.0423,
        50: 2.0086,
        100: 1.9840,
        120: 1.9799,
    }
    for df, expected in ref_table.items():
        val = get_t_critical_value(df, confidence=0.95)
        assert abs(val - expected) < 1e-4, f"Falha em df={df}: obtido {val}, esperado {expected}"


def test_t_critical_value_asymptotic_large_df():
    """Valida a aproximação assintótica para df > 120 (df=200)."""
    val = get_t_critical_value(200, confidence=0.95)
    # 1.95996 + 2.376 / 200 = 1.97184 -> round 1.9718
    assert abs(val - 1.9718) < 1e-4


def test_t_critical_value_unsupported_confidence_raises():
    """Confidence != 0.95 deve levantar ValueError explicitamente."""
    with pytest.raises(ValueError, match="Confidence 0.9 não suportado"):
        get_t_critical_value(10, confidence=0.90)


# ============================================================
# 2. PARTE E — Testes de Amostras Conhecidas de Expectancy CI
# ============================================================

def test_expectancy_ci_n_equals_two():
    """Amostra n=2 com trades [2.0, -1.0]."""
    trades = [2.0, -1.0]
    res = compute_t_student_expectancy_interval(trades)
    assert res["expectancy_r"] == 0.50
    assert abs(res["sample_std_r"] - 2.12) <= 0.01
    assert abs(res["standard_error_r"] - 1.50) <= 0.01
    # df=1, t_crit=12.7062 -> margin = 12.7062 * 1.50 = 19.0593 -> [-18.56, 19.56]
    assert res["expectancy_ci_95"][0] == -18.56
    assert res["expectancy_ci_95"][1] == 19.56


def test_expectancy_ci_small_mixed_sample():
    """Amostra n=5: [2.0, 2.0, -1.0, -1.0, 2.0] (mean = 0.80)."""
    trades = [2.0, 2.0, -1.0, -1.0, 2.0]
    res = compute_t_student_expectancy_interval(trades)
    assert res["expectancy_r"] == 0.80
    assert res["expectancy_ci_95"][0] < 0.80
    assert res["expectancy_ci_95"][1] > 0.80


def test_expectancy_ci_larger_sample():
    """Amostra n=20: 8 wins (+2R) e 12 losses (-1R) (mean = +0.20)."""
    trades = [2.0] * 8 + [-1.0] * 12
    res = compute_t_student_expectancy_interval(trades)
    assert res["expectancy_r"] == 0.20
    assert res["expectancy_ci_95"][0] < 0.20
    assert res["expectancy_ci_95"][1] > 0.20


# ============================================================
# 3. Pure Math & Edge Cases
# ============================================================

def test_wilson_score_zero_total():
    wr, ci = compute_wilson_score_interval(0, 0)
    assert wr is None
    assert ci == (None, None)


def test_wilson_score_zero_wins():
    wr, ci = compute_wilson_score_interval(0, 10)
    assert wr == 0.0
    assert ci[0] == 0.0
    assert ci[1] > 0.0
    assert ci[1] <= 100.0


def test_wilson_score_all_wins():
    wr, ci = compute_wilson_score_interval(10, 10)
    assert wr == 100.0
    assert ci[0] < 100.0
    assert ci[0] >= 0.0
    assert ci[1] == 100.0


def test_t_student_zero_trades():
    res = compute_t_student_expectancy_interval([])
    assert res["expectancy_r"] is None
    assert res["expectancy_ci_95"] == [None, None]


def test_t_student_one_trade():
    res = compute_t_student_expectancy_interval([2.0])
    assert res["expectancy_r"] == 2.0
    assert res["sample_std_r"] is None
    assert res["expectancy_ci_95"] == [None, None]


def test_t_student_zero_variance():
    res = compute_t_student_expectancy_interval([2.0, 2.0, 2.0])
    assert res["expectancy_r"] == 2.0
    assert res["zero_variance"] is True
    assert res["expectancy_ci_95"] == [2.0, 2.0]


# ============================================================
# 4. Classificações
# ============================================================

def test_classify_statistical_evidence():
    assert classify_statistical_evidence(0, None, [None, None]) == "NOT_EVALUATED"
    assert classify_statistical_evidence(1, 2.0, [None, None]) == "INCONCLUSIVE"
    assert classify_statistical_evidence(10, 0.50, [-0.50, 1.50]) == "POSITIVE_POINT_ESTIMATE_UNCONFIRMED"
    assert classify_statistical_evidence(10, -0.50, [-1.50, 0.50]) == "NEGATIVE_POINT_ESTIMATE_UNCONFIRMED"
    assert classify_statistical_evidence(100, 0.50, [0.10, 0.90]) == "POSITIVE_EDGE_EVIDENCE"
    assert classify_statistical_evidence(100, -0.50, [-0.90, -0.10]) == "NEGATIVE_EDGE_EVIDENCE"


def test_classify_operational_maturity():
    assert classify_operational_maturity(0) == "STAGE_1_INITIAL"
    assert classify_operational_maturity(19) == "STAGE_1_INITIAL"
    assert classify_operational_maturity(20) == "STAGE_2_EARLY"
    assert classify_operational_maturity(49) == "STAGE_2_EARLY"
    assert classify_operational_maturity(50) == "STAGE_3_ACCUMULATING"
    assert classify_operational_maturity(99) == "STAGE_3_ACCUMULATING"
    assert classify_operational_maturity(100) == "STAGE_4_EXTENDED"


def test_classify_statistical_precision():
    assert classify_statistical_precision(None) == "VERY_LOW"
    assert classify_statistical_precision(1.20) == "VERY_LOW"
    assert classify_statistical_precision(0.80) == "LOW"
    assert classify_statistical_precision(0.50) == "MODERATE"
    assert classify_statistical_precision(0.35) == "HIGH"


def test_classify_historical_compatibility():
    assert classify_historical_compatibility(0.1367, [None, None]) == "NOT_EVALUATED"
    assert classify_historical_compatibility(0.1367, [-0.10, 0.40]) == "REFERENCE_WITHIN_CI"
    assert classify_historical_compatibility(0.1367, [0.20, 0.80]) == "REFERENCE_OUTSIDE_CI"


# ============================================================
# 5. PARTE L — Testes de Scanner Coverage Sem Falsa Precisão
# ============================================================

def test_scanner_coverage_is_null_without_telemetry(mock_perf_engine):
    """39 scanners configurados não devem produzir scanner_coverage = 1.0 sem telemetria temporal."""
    engine = ShadowStatisticalValidationEngine(perf_engine=mock_perf_engine)
    snap = engine.build_validation_snapshot()

    # scanner_coverage deve ser estritamente None (null)
    assert snap.measurement["scanner_coverage"] is None
    # Deve conter a advertência de cobertura indisponível
    assert any("SCANNER_COVERAGE_UNAVAILABLE" in w for w in snap.operational_policy["warnings"])
    # Deve conter o reason code correspondente
    reason_codes = [r["code"] for r in snap.decision["reason_codes"]]
    assert "SCANNER_COVERAGE_UNAVAILABLE" in reason_codes
    # Quality state deve ser DATA_QUALITY_WARNING
    assert snap.operational_policy["quality_state"] == "DATA_QUALITY_WARNING"


def test_engine_human_review_always_true(mock_perf_engine):
    events = [make_terminal_event(f"e{i}", "TARGET_2R" if i <= 7 else "STOPPED") for i in range(10)]
    mock_perf_engine.store.list_history_events.return_value = events

    engine = ShadowStatisticalValidationEngine(perf_engine=mock_perf_engine)
    snap = engine.build_validation_snapshot()

    assert snap.decision["requires_human_review"] is True
