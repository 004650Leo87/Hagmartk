"""Hagmartk Shadow Decision & Evidence Layer V1 (Fase 4E).

Camada de julgamento quantitativo observacional e classificação da força da evidência prospectiva.
Respeita o princípio arquitetural:
HDF -> Detecta
Shadow -> Observa
Telemetry -> Prova que observou
Statistical Engine -> Mede
Intelligence -> Consolida
Decision & Evidence -> Classifica a força da evidência (READ-ONLY)
Humano -> Decide

REGRAS RÍGIDAS:
1. SEM SCORE MÁGICO / PESOS INVENTADOS. Usar regras explícitas e estados discretos.
2. NUNCA EXECUTAR AÇÃO (No side effects: sem broker, sem Telegram, sem mudar parâmetros HDF).
3. 100% DETERMINÍSTICO E LOCAL (Sem chamadas a APIs de IA generativa externas).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from backend.core.time_utils import now_utc_str
from backend.services.shadow_intelligence import ShadowIntelligenceEngine, ShadowIntelligenceSnapshot
from backend.services.shadow_statistical_validation import ShadowStatisticalValidationEngine
from backend.services.shadow_store import ShadowStoreRepository


HUMAN_REASON_DESCRIPTIONS: Dict[str, str] = {
    "NO_COMPLETED_TRADES": "Ainda não existem trades terminais concluídos na amostra prospectiva viva.",
    "SAMPLE_INSUFFICIENT": "A amostra prospectiva possui menos de 20 trades concluídos.",
    "SAMPLE_EARLY": "A amostra prospectiva ainda é inicial (entre 20 e 49 trades).",
    "SAMPLE_USABLE": "A amostra prospectiva atingiu quantidade utilizável (entre 50 e 99 trades).",
    "SAMPLE_MATURE": "A amostra prospectiva atingiu maturidade estatística (100+ trades).",
    "SCANNER_COVERAGE_UNKNOWN": "Telemetria temporal do scanner indisponível ou sem histórico.",
    "SCANNER_COVERAGE_DEGRADED": "A cobertura operacional do scanner ficou abaixo do SLA de 95%.",
    "DATA_QUALITY_PARTIAL": "Existem avisos parciais de qualidade nos dados observados.",
    "DATA_QUALITY_VALID": "Os dados prospectivos cumprem todos os requisitos de integridade.",
    "EXPECTANCY_POSITIVE": "A expectativa matemática prospectiva observada é positiva (> 0R).",
    "EXPECTANCY_NEGATIVE": "A expectativa matemática prospectiva observada é negativa (< 0R).",
    "EXPECTANCY_CI_CROSSES_ZERO": "O intervalo de confiança de 95% ainda inclui valores nulos ou negativos.",
    "EXPECTANCY_CI_POSITIVE": "O intervalo de confiança de 95% é inteiramente positivo (> 0R).",
    "HISTORICAL_PROSPECTIVE_CONSISTENT": "O comportamento prospectivo é estatisticamente coerente com a referência histórica.",
    "HISTORICAL_PROSPECTIVE_DIVERGING": "O comportamento prospectivo diverge da referência histórica congelada.",
    "HIGH_INVALIDATION_RATE": "A taxa de invalidação de setups pré-ativação está elevada (> 40%).",
    "NO_SIDE_EFFECTS": "Camada 100% observacional read-only; nenhuma ordem, sinal externo ou alteração foi executada.",
}


@dataclass
class EvidenceObject:
    generated_at: str
    strategy_id: str
    candidate_id: str
    candidate_version: str

    observational_status: str
    evidence_state: str

    sample: Dict[str, Any]
    data_quality: Dict[str, Any]
    performance: Dict[str, Any]
    historical_comparison: Dict[str, Any]

    reason_codes: List[str]
    human_reasons: List[str]

    segments: Dict[str, Any] = field(default_factory=dict)
    contradictions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowDecisionEvidenceEngine:
    """Motor determinístico de decisão e classificação de evidência prospectiva."""

    def __init__(
        self,
        store: Optional[ShadowStoreRepository] = None,
        intel_engine: Optional[ShadowIntelligenceEngine] = None,
    ) -> None:
        self.store = store or ShadowStoreRepository()
        self.intel_engine = intel_engine or ShadowIntelligenceEngine(store=self.store)

    def evaluate_evidence(self, candidate_id: str = "hdf_dvp_exit_2r") -> EvidenceObject:
        now_str = now_utc_str()

        # 1. Obter snapshot da ShadowIntelligenceEngine (fonte canônica de métricas)
        intel_snap = self.intel_engine.build_intelligence_snapshot(candidate_id=candidate_id)

        # 2. Extrair dados necessários das 9 camadas de inteligência
        term_cnt = intel_snap.sample_size.get("terminal_trades_count", 0)
        sample_class = intel_snap.sample_size.get("status", "INSUFFICIENT")

        glob_health = intel_snap.scanner_health.get("global", {})
        coverage = glob_health.get("coverage", None)

        quality_ctx = intel_snap.data_quality.get("quality_context", "UNAVAILABLE")

        fin_perf = intel_snap.prospective_performance.get("financial", {})
        exp_r = fin_perf.get("expectancy_r", None)

        stat_ev = intel_snap.prospective_performance.get("statistical_evidence", {})
        ci_95 = stat_ev.get("expectancy_ci_95", [None, None])
        ci_lower = ci_95[0] if ci_95 and len(ci_95) > 0 else None
        ci_upper = ci_95[1] if ci_95 and len(ci_95) > 1 else None

        hist_comp = intel_snap.historical_comparison.get("status", "INSUFFICIENT_DATA")

        rates = intel_snap.prospective_funnel.get("rates", {})
        invalidation_rate = rates.get("invalidation_rate_pct", 0.0)

        # 3. Construir Reason Codes determinísticos
        reason_codes: List[str] = []
        contradictions: List[str] = []

        if term_cnt == 0:
            reason_codes.append("NO_COMPLETED_TRADES")
            reason_codes.append("SAMPLE_INSUFFICIENT")
        elif sample_class == "INSUFFICIENT":
            reason_codes.append("SAMPLE_INSUFFICIENT")
        elif sample_class == "EARLY":
            reason_codes.append("SAMPLE_EARLY")
        elif sample_class == "USABLE":
            reason_codes.append("SAMPLE_USABLE")
        elif sample_class == "MATURE":
            reason_codes.append("SAMPLE_MATURE")

        if coverage is None:
            reason_codes.append("SCANNER_COVERAGE_UNKNOWN")
        elif coverage < 0.95:
            reason_codes.append("SCANNER_COVERAGE_DEGRADED")

        if quality_ctx == "PARTIAL":
            reason_codes.append("DATA_QUALITY_PARTIAL")
        elif quality_ctx == "VALID":
            reason_codes.append("DATA_QUALITY_VALID")

        if exp_r is not None:
            if exp_r > 0:
                reason_codes.append("EXPECTANCY_POSITIVE")
            else:
                reason_codes.append("EXPECTANCY_NEGATIVE")

        if ci_lower is not None and ci_upper is not None:
            if ci_lower <= 0 <= ci_upper:
                reason_codes.append("EXPECTANCY_CI_CROSSES_ZERO")
                if exp_r is not None and exp_r > 0:
                    contradictions.append(
                        "Expectativa pontual positiva, porém o intervalo de confiança de 95% ainda cruza zero."
                    )
            elif ci_lower > 0:
                reason_codes.append("EXPECTANCY_CI_POSITIVE")

        if hist_comp == "CONSISTENT":
            reason_codes.append("HISTORICAL_PROSPECTIVE_CONSISTENT")
        elif hist_comp == "DIVERGING":
            reason_codes.append("HISTORICAL_PROSPECTIVE_DIVERGING")

        if invalidation_rate > 40.0:
            reason_codes.append("HIGH_INVALIDATION_RATE")

        if coverage is not None and coverage < 0.95 and exp_r is not None and exp_r > 0:
            contradictions.append(
                "Expectativa prospectiva positiva observada em cenário de telemetria do scanner degradada (< 95%)."
            )

        reason_codes.append("NO_SIDE_EFFECTS")

        # 4. Determinar Evidence State determinístico (Hierarquia)
        if term_cnt < 20 or coverage is None:
            evidence_state = "INSUFFICIENT_EVIDENCE"
        elif coverage < 0.80 or quality_ctx in ("UNAVAILABLE", "INSUFFICIENT"):
            evidence_state = "DEGRADED_EVIDENCE"
        elif sample_class == "EARLY":
            evidence_state = "EARLY_EVIDENCE"
        elif ci_lower is not None and ci_upper is not None and (ci_lower <= 0 <= ci_upper):
            evidence_state = "CONFLICTING_EVIDENCE" if sample_class in ("USABLE", "MATURE") else "EARLY_EVIDENCE"
        elif sample_class == "USABLE":
            evidence_state = "DEVELOPING_EVIDENCE"
        elif sample_class == "MATURE" and exp_r is not None and exp_r > 0 and ci_lower is not None and ci_lower > 0 and coverage >= 0.95 and hist_comp == "CONSISTENT":
            evidence_state = "ROBUST_EVIDENCE"
        else:
            evidence_state = "DEVELOPING_EVIDENCE"

        # 5. Determinar Observational Status determinístico (Hierarquia de Julgamento)
        if term_cnt < 20:
            observational_status = "COLLECTING_DATA"
        elif quality_ctx in ("UNAVAILABLE", "INSUFFICIENT") or (coverage is not None and coverage < 0.95):
            observational_status = "DATA_QUALITY_WARNING"
        elif sample_class == "EARLY":
            observational_status = "EARLY_VALIDATION"
        elif hist_comp == "DIVERGING" or (exp_r is not None and exp_r < -0.20):
            observational_status = "EVIDENCE_DIVERGING"
        elif hist_comp == "CONSISTENT" and exp_r is not None and exp_r > 0 and ci_lower is not None and ci_lower > 0:
            observational_status = "EVIDENCE_CONSISTENT"
        else:
            observational_status = "VALIDATING"

        # 6. Gerar explicações humanas
        human_reasons = [HUMAN_REASON_DESCRIPTIONS.get(code, code) for code in reason_codes]

        # 7. Estruturar o Evidence Object completo
        sample_dict = {
            "size": term_cnt,
            "classification": sample_class,
            "thresholds": intel_snap.sample_size.get("thresholds", {}),
        }

        data_quality_dict = {
            "state": quality_ctx,
            "scanner_coverage": coverage,
            "failed_scanner_checks": glob_health.get("failed_checks", 0),
        }

        performance_dict = {
            "expectancy_r": exp_r,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "win_rate_pct": fin_perf.get("win_rate_pct", None),
            "profit_factor": fin_perf.get("profit_factor", None),
            "total_r": fin_perf.get("total_r", 0.0),
            "max_drawdown_r": fin_perf.get("max_drawdown_r", 0.0),
        }

        historical_comparison_dict = {
            "state": hist_comp,
            "reason": intel_snap.historical_comparison.get("reason", ""),
        }

        return EvidenceObject(
            generated_at=now_str,
            strategy_id="HDF",
            candidate_id=candidate_id,
            candidate_version=intel_snap.candidate_version,
            observational_status=observational_status,
            evidence_state=evidence_state,
            sample=sample_dict,
            data_quality=data_quality_dict,
            performance=performance_dict,
            historical_comparison=historical_comparison_dict,
            reason_codes=reason_codes,
            human_reasons=human_reasons,
            segments=intel_snap.segmentation,
            contradictions=contradictions,
        )
