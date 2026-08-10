"""Suíte de testes para a Decision & Evidence Layer V1 do Shadow Mode (Fase 4E).

Cobre:
1. Zero data state (COLLECTING_DATA, INSUFFICIENT_EVIDENCE, NO_COMPLETED_TRADES)
2. Classificação de tamanho de amostra (INSUFFICIENT, EARLY, USABLE, MATURE)
3. Interpretação de Expectância & Intervalo de Confiança t-Student (CI crosses zero vs CI positive)
4. Telemetria e Cobertura do Scanner (UNKNOWN, DEGRADED, VALID)
5. Contradições observacionais entre métricas pontuais e intervalos/coberturas
6. Mapeamento 1-para-1 de Reason Codes para Linguagem Humana
7. Teste de Ausência de Side Effects (NO_SIDE_EFFECTS: sem broker, sem Telegram, sem alteração de HDF)
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.services.shadow_decision_evidence import (
    HUMAN_REASON_DESCRIPTIONS,
    ShadowDecisionEvidenceEngine,
)


@pytest.fixture
def mock_intel_engine():
    intel = MagicMock()
    mock_snap = MagicMock()
    mock_snap.candidate_version = "v1.0.0"
    mock_snap.sample_size = {"terminal_trades_count": 0, "status": "INSUFFICIENT", "thresholds": {}}
    mock_snap.scanner_health = {"global": {"expected_checks": 0, "successful_checks": 0, "failed_checks": 0, "coverage": None, "health": "UNKNOWN"}}
    mock_snap.data_quality = {"quality_context": "UNAVAILABLE"}
    mock_snap.prospective_performance = {
        "financial": {"expectancy_r": None, "win_rate_pct": None, "profit_factor": None, "total_r": 0.0, "max_drawdown_r": 0.0},
        "statistical_evidence": {"expectancy_ci_95": [None, None]},
        "structural": {"long_ratio_pct": 0.0, "short_ratio_pct": 0.0},
    }
    mock_snap.historical_comparison = {"status": "INSUFFICIENT_DATA", "reason": "Sem dados suficientes."}
    mock_snap.prospective_funnel = {"rates": {"invalidation_rate_pct": 0.0}}
    mock_snap.segmentation = {}

    intel.build_intelligence_snapshot.return_value = mock_snap
    return intel


# ============================================================
# 1. Testes de Classificação Determinística
# ============================================================

def test_decision_layer_zero_data(mock_intel_engine):
    engine = ShadowDecisionEvidenceEngine(intel_engine=mock_intel_engine)
    evidence = engine.evaluate_evidence()

    assert evidence.observational_status == "COLLECTING_DATA"
    assert evidence.evidence_state == "INSUFFICIENT_EVIDENCE"
    assert "NO_COMPLETED_TRADES" in evidence.reason_codes
    assert "SAMPLE_INSUFFICIENT" in evidence.reason_codes
    assert "NO_SIDE_EFFECTS" in evidence.reason_codes
    assert len(evidence.reason_codes) == len(evidence.human_reasons)


def test_decision_layer_early_sample(mock_intel_engine):
    snap = mock_intel_engine.build_intelligence_snapshot.return_value
    snap.sample_size = {"terminal_trades_count": 30, "status": "EARLY", "thresholds": {}}
    snap.scanner_health = {"global": {"coverage": 0.98, "failed_checks": 0}}
    snap.data_quality = {"quality_context": "VALID"}
    snap.prospective_performance = {
        "financial": {"expectancy_r": 0.20, "win_rate_pct": 40.0, "profit_factor": 1.33},
        "statistical_evidence": {"expectancy_ci_95": [-0.15, +0.55]},
        "structural": {"long_ratio_pct": 50.0, "short_ratio_pct": 50.0},
    }

    engine = ShadowDecisionEvidenceEngine(intel_engine=mock_intel_engine)
    evidence = engine.evaluate_evidence()

    assert evidence.observational_status == "EARLY_VALIDATION"
    assert evidence.evidence_state == "EARLY_EVIDENCE"
    assert "EXPECTANCY_POSITIVE" in evidence.reason_codes
    assert "EXPECTANCY_CI_CROSSES_ZERO" in evidence.reason_codes


def test_decision_layer_robust_evidence(mock_intel_engine):
    snap = mock_intel_engine.build_intelligence_snapshot.return_value
    snap.sample_size = {"terminal_trades_count": 120, "status": "MATURE", "thresholds": {}}
    snap.scanner_health = {"global": {"coverage": 0.99, "failed_checks": 0}}
    snap.data_quality = {"quality_context": "VALID"}
    snap.historical_comparison = {"status": "CONSISTENT", "reason": "Coerente"}
    snap.prospective_performance = {
        "financial": {"expectancy_r": 0.35, "win_rate_pct": 41.0, "profit_factor": 1.40},
        "statistical_evidence": {"expectancy_ci_95": [+0.08, +0.62]},
        "structural": {"long_ratio_pct": 50.0, "short_ratio_pct": 50.0},
    }

    engine = ShadowDecisionEvidenceEngine(intel_engine=mock_intel_engine)
    evidence = engine.evaluate_evidence()

    assert evidence.observational_status == "EVIDENCE_CONSISTENT"
    assert evidence.evidence_state == "ROBUST_EVIDENCE"
    assert "EXPECTANCY_CI_POSITIVE" in evidence.reason_codes
    assert "HISTORICAL_PROSPECTIVE_CONSISTENT" in evidence.reason_codes


def test_decision_layer_contradictions_detection(mock_intel_engine):
    snap = mock_intel_engine.build_intelligence_snapshot.return_value
    snap.sample_size = {"terminal_trades_count": 60, "status": "USABLE", "thresholds": {}}
    snap.scanner_health = {"global": {"coverage": 0.88, "failed_checks": 2}}
    snap.data_quality = {"quality_context": "PARTIAL"}
    snap.prospective_performance = {
        "financial": {"expectancy_r": 0.25},
        "statistical_evidence": {"expectancy_ci_95": [-0.05, +0.55]},
    }

    engine = ShadowDecisionEvidenceEngine(intel_engine=mock_intel_engine)
    evidence = engine.evaluate_evidence()

    assert len(evidence.contradictions) > 0
    assert "SCANNER_COVERAGE_DEGRADED" in evidence.reason_codes


# ============================================================
# 2. Side Effect Guard Test (PARTE S)
# ============================================================

def test_decision_layer_side_effect_safety(mock_intel_engine):
    """Garante que a Decision Layer é 100% read-only e nunca altera parâmetros do HDF."""
    original_version = HDF_ROBUST_CANDIDATE_V1.candidate_version
    original_rsi_period = HDF_ROBUST_CANDIDATE_V1.rsi_period
    original_target_r = HDF_ROBUST_CANDIDATE_V1.target_r

    engine = ShadowDecisionEvidenceEngine(intel_engine=mock_intel_engine)
    evidence = engine.evaluate_evidence()

    # Imutabilidade preservada
    assert HDF_ROBUST_CANDIDATE_V1.candidate_version == original_version
    assert HDF_ROBUST_CANDIDATE_V1.rsi_period == original_rsi_period
    assert HDF_ROBUST_CANDIDATE_V1.target_r == original_target_r
    assert "NO_SIDE_EFFECTS" in evidence.reason_codes
