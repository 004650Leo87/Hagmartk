"""Hagmartk Shadow Intelligence & Prospective Validation Engine V1 (Fase 4D).

Serviço unificado de inteligência e observabilidade operacional prospectiva.
Consolida as 9 camadas de validação prospectiva do ROBUST_CANDIDATE:
1. Scanner Health (Global, por Asset Class, por Timeframe, por Combinação)
2. Funil Prospectivo de Conversão (Detected -> Armed -> Activated -> Completed / Stopped / Invalidated)
3. Métricas Estruturais & Duracionais Prospectivas
4. Segmentações Multidimensionais (Symbol, Timeframe, Asset Class, Direction)
5. Comparação Observacional Histórico vs Prospectivo (CONSISTENT, WATCH, DIVERGING, INSUFFICIENT_DATA)
6. Classificação Determinística do Tamanho da Amostra (INSUFFICIENT, EARLY, USABLE, MATURE)
7. Auditoria de Qualidade dos Dados & Telemetria (VALID, PARTIAL, INSUFFICIENT, UNAVAILABLE)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional

from backend.core.time_utils import now_utc_str, parse_utc_timestamp
from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.shadow_models import ShadowEvent, ShadowState
from backend.services.shadow_performance import ShadowPerformanceEngine, ShadowPerformanceSnapshot
from backend.services.shadow_statistical_validation import ShadowStatisticalValidationEngine
from backend.services.shadow_store import ShadowStoreRepository
from backend.services.shadow_scanner import SHADOW_ASSETS, SHADOW_TIMEFRAMES, get_asset_class


# Thresholds de Tamanho de Amostra (Camada 6)
SAMPLE_SIZE_THRESHOLDS = {
    "INSUFFICIENT": 20,
    "EARLY": 50,
    "USABLE": 100,
}


def classify_sample_size(n_terminal: int) -> str:
    """Classifica deterministicamente a maturidade do tamanho da amostra prospectiva."""
    if n_terminal < SAMPLE_SIZE_THRESHOLDS["INSUFFICIENT"]:
        return "INSUFFICIENT"
    if n_terminal < SAMPLE_SIZE_THRESHOLDS["EARLY"]:
        return "EARLY"
    if n_terminal < SAMPLE_SIZE_THRESHOLDS["USABLE"]:
        return "USABLE"
    return "MATURE"


def classify_historical_comparison(
    n_terminal: int,
    prosp_expectancy_r: Optional[float],
    prosp_win_rate: Optional[float],
    hist_expectancy_r: float = 0.1367,
    hist_win_rate: float = 37.89,
) -> Dict[str, Any]:
    """Compara métricas equivalentes entre o histórico do ROBUST_CANDIDATE e a amostra prospectiva viva."""
    if n_terminal < 20 or prosp_expectancy_r is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "Amostra prospectiva insuficiente para comparação observacional (< 20 trades).",
            "comparable_metrics": {
                "expectancy_r": {"historical": hist_expectancy_r, "prospective": prosp_expectancy_r, "delta": None},
                "win_rate_pct": {"historical": hist_win_rate, "prospective": prosp_win_rate, "delta": None},
            },
        }

    delta_exp = round(prosp_expectancy_r - hist_expectancy_r, 4)
    delta_wr = round(prosp_win_rate - hist_win_rate, 2) if prosp_win_rate is not None else None

    if prosp_expectancy_r >= (hist_expectancy_r - 0.10):
        status = "CONSISTENT"
        reason = "Comportamento prospectivo coerente com a expectativa histórica."
    elif prosp_expectancy_r >= -0.20:
        status = "WATCH"
        reason = "Expectancy prospectiva abaixo do histórico, requer acompanhamento continuado."
    else:
        status = "DIVERGING"
        reason = "Expectancy prospectiva diverge significativamente do histórico de referência."

    return {
        "status": status,
        "reason": reason,
        "comparable_metrics": {
            "expectancy_r": {"historical": hist_expectancy_r, "prospective": prosp_expectancy_r, "delta": delta_exp},
            "win_rate_pct": {"historical": hist_win_rate, "prospective": prosp_win_rate, "delta": delta_wr},
        },
    }


def classify_data_quality_context(
    coverage: Optional[float],
    same_bar_rate: float,
    sample_size_status: str,
    failed_checks: int,
) -> str:
    """Classifica o contexto global de qualidade e integridade dos dados prospectivos."""
    if coverage is None:
        return "UNAVAILABLE"
    if coverage < 0.80 or sample_size_status == "INSUFFICIENT":
        return "INSUFFICIENT"
    if coverage < 0.95 or same_bar_rate > 20.0 or failed_checks > 0:
        return "PARTIAL"
    return "VALID"


@dataclass
class ShadowIntelligenceSnapshot:
    generated_at: str
    candidate_id: str
    candidate_version: str

    scanner_health: Dict[str, Any]
    prospective_funnel: Dict[str, Any]
    prospective_performance: Dict[str, Any]
    segmentation: Dict[str, Any]
    sample_size: Dict[str, Any]
    historical_comparison: Dict[str, Any]
    data_quality: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowIntelligenceEngine:
    """Motor de inteligência e validação operacional prospectiva do Shadow Mode."""

    def __init__(
        self,
        store: Optional[ShadowStoreRepository] = None,
        perf_engine: Optional[ShadowPerformanceEngine] = None,
        stat_engine: Optional[ShadowStatisticalValidationEngine] = None,
    ) -> None:
        self.store = store or ShadowStoreRepository()
        self.perf_engine = perf_engine or ShadowPerformanceEngine(store=self.store)
        self.stat_engine = stat_engine or ShadowStatisticalValidationEngine(perf_engine=self.perf_engine)

    def build_intelligence_snapshot(
        self, candidate_id: str = "hdf_dvp_exit_2r"
    ) -> ShadowIntelligenceSnapshot:
        now_str = now_utc_str()

        # 1. Telemetria & Scanner Health
        telemetry = self.store.get_shadow_telemetry(candidate_id=candidate_id)
        glob_telem = telemetry.get("global", {})
        comb_telem = telemetry.get("combinations", [])

        # Agregações por Asset Class e por Timeframe
        health_by_asset_class: Dict[str, Dict[str, Any]] = {}
        health_by_timeframe: Dict[str, Dict[str, Any]] = {}

        for comb in comb_telem:
            ac = comb.get("asset_class", "UNKNOWN")
            tf = comb.get("timeframe", "UNKNOWN")

            # Por Asset Class
            if ac not in health_by_asset_class:
                health_by_asset_class[ac] = {"expected": 0, "successful": 0, "failed": 0}
            health_by_asset_class[ac]["expected"] += comb.get("expected_checks", 0)
            health_by_asset_class[ac]["successful"] += comb.get("successful_checks", 0)
            health_by_asset_class[ac]["failed"] += comb.get("failed_checks", 0)

            # Por Timeframe
            if tf not in health_by_timeframe:
                health_by_timeframe[tf] = {"expected": 0, "successful": 0, "failed": 0}
            health_by_timeframe[tf]["expected"] += comb.get("expected_checks", 0)
            health_by_timeframe[tf]["successful"] += comb.get("successful_checks", 0)
            health_by_timeframe[tf]["failed"] += comb.get("failed_checks", 0)

        for ac, data in health_by_asset_class.items():
            exp = data["expected"]
            succ = data["successful"]
            cov = round(succ / exp, 4) if exp > 0 else None
            data["coverage"] = cov
            if exp == 0:
                data["health"] = "UNKNOWN"
            elif cov is not None and cov >= 0.95:
                data["health"] = "HEALTHY"
            elif cov is not None and cov > 0.0:
                data["health"] = "DEGRADED"
            else:
                data["health"] = "UNAVAILABLE"

        for tf, data in health_by_timeframe.items():
            exp = data["expected"]
            succ = data["successful"]
            cov = round(succ / exp, 4) if exp > 0 else None
            data["coverage"] = cov
            if exp == 0:
                data["health"] = "UNKNOWN"
            elif cov is not None and cov >= 0.95:
                data["health"] = "HEALTHY"
            elif cov is not None and cov > 0.0:
                data["health"] = "DEGRADED"
            else:
                data["health"] = "UNAVAILABLE"

        scanner_health = {
            "global": glob_telem,
            "by_asset_class": health_by_asset_class,
            "by_timeframe": health_by_timeframe,
            "combinations": comb_telem,
        }

        # 2. Performance & Validation Snapshots existentes
        perf_snap = self.perf_engine.build_snapshot(candidate_id=candidate_id)
        stat_snap = self.stat_engine.build_validation_snapshot(candidate_id=candidate_id)

        # 3. Funil Prospectivo Completo
        opps = perf_snap.prospective_opportunities
        act_cnt = perf_snap.activated_count
        term_cnt = perf_snap.terminal_trades_count
        wins = perf_snap.wins_count
        losses = perf_snap.losses_count
        expired = perf_snap.expired_pre_activation_count
        invalidated = perf_snap.invalidated_pre_activation_count

        armed_cnt = act_cnt + expired + invalidated

        act_rate = round((act_cnt / armed_cnt * 100.0), 2) if armed_cnt > 0 else 0.0
        completion_rate = round((term_cnt / act_cnt * 100.0), 2) if act_cnt > 0 else 0.0
        exit_2r_rate = round((wins / term_cnt * 100.0), 2) if term_cnt > 0 else 0.0
        invalidation_rate = round((invalidated / armed_cnt * 100.0), 2) if armed_cnt > 0 else 0.0

        prospective_funnel = {
            "detected_opportunities": opps,
            "armed_setups": armed_cnt,
            "activated_trades": act_cnt,
            "terminal_trades": term_cnt,
            "completed_target_2R": wins,
            "completed_stopped": losses,
            "invalidated_pre_activation": invalidated,
            "expired_pre_activation": expired,
            "rates": {
                "activation_rate_pct": act_rate,
                "invalidation_rate_pct": invalidation_rate,
                "completion_rate_pct": completion_rate,
                "exit_2r_hit_rate_pct": exit_2r_rate,
            },
        }

        # 4. Métricas Prospectivas Estruturais
        long_count = 0
        short_count = 0
        all_events = self.store.list_history_events()

        for evt in all_events:
            if evt.candidate_id == candidate_id and not (evt.metadata and evt.metadata.get("bootstrap_detected")):
                if evt.direction == "BULLISH":
                    long_count += 1
                elif evt.direction == "BEARISH":
                    short_count += 1

        total_signals = long_count + short_count
        long_pct = round((long_count / total_signals * 100.0), 1) if total_signals > 0 else 0.0
        short_pct = round((short_count / total_signals * 100.0), 1) if total_signals > 0 else 0.0

        prospective_performance = {
            "financial": {
                "expectancy_r": perf_snap.expectancy_r,
                "win_rate_pct": perf_snap.win_rate,
                "profit_factor": perf_snap.profit_factor,
                "total_r": perf_snap.total_r,
                "max_drawdown_r": perf_snap.max_drawdown_r,
            },
            "statistical_evidence": stat_snap.statistical_evidence,
            "structural": {
                "total_signals_detected": total_signals,
                "long_signals": long_count,
                "short_signals": short_count,
                "long_ratio_pct": long_pct,
                "short_ratio_pct": short_pct,
            },
            "duration": {
                "avg_duration_bars": perf_snap.avg_duration_bars,
                "avg_duration_seconds": perf_snap.avg_duration_seconds,
            },
            "excursion_r": {
                "avg_mae_r": perf_snap.avg_mae_r,
                "avg_mfe_r": perf_snap.avg_mfe_r,
            },
        }

        # 5. Segmentação Multidimensional
        segmentation = perf_snap.breakdowns

        # 6. Classificação do Tamanho da Amostra (Camada 6)
        sample_size_status = classify_sample_size(term_cnt)
        sample_size_info = {
            "terminal_trades_count": term_cnt,
            "status": sample_size_status,
            "thresholds": SAMPLE_SIZE_THRESHOLDS,
        }

        # 7. Comparação Histórico vs Prospectivo (Camada 5)
        hist_comp = classify_historical_comparison(
            n_terminal=term_cnt,
            prosp_expectancy_r=perf_snap.expectancy_r,
            prosp_win_rate=perf_snap.win_rate,
        )

        # 8. Qualidade dos Dados & Contexto (Camada 7)
        coverage_val = glob_telem.get("coverage", None)
        failed_checks_val = glob_telem.get("failed_checks", 0)
        same_bar_rate_val = stat_snap.measurement.get("same_bar_rate", 0.0)

        data_quality_context = classify_data_quality_context(
            coverage=coverage_val,
            same_bar_rate=same_bar_rate_val,
            sample_size_status=sample_size_status,
            failed_checks=failed_checks_val,
        )

        data_quality = {
            "quality_context": data_quality_context,
            "scanner_coverage": coverage_val,
            "same_bar_ambiguous_rate_pct": same_bar_rate_val,
            "failed_scanner_checks": failed_checks_val,
            "warnings": stat_snap.operational_policy.get("warnings", []),
        }

        return ShadowIntelligenceSnapshot(
            generated_at=now_str,
            candidate_id=candidate_id,
            candidate_version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
            scanner_health=scanner_health,
            prospective_funnel=prospective_funnel,
            prospective_performance=prospective_performance,
            segmentation=segmentation,
            sample_size=sample_size_info,
            historical_comparison=hist_comp,
            data_quality=data_quality,
        )
