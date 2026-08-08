from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class RobustCandidateSpec:
    """Especificação imutável e versionada de um Candidato Robusto aprovado no Stage 2."""

    candidate_id: str = "hdf_dvp_exit_2r"
    candidate_version: str = "1.0.0"
    display_name: str = "Hagmartk Divergence Flow — Candidate V1"
    strategy_id: str = "hagmartk_divergence_flow"
    variant: str = "HDF_DVP"
    exit_policy: str = "EXIT_2R"

    rsi_method: str = "Wilder"
    rsi_period: int = 14
    pivot_left: int = 2
    pivot_right: int = 2
    min_bars_between_pivots: int = 5
    max_bars_between_pivots: int = 50
    volume_min_relative: float = 1.0
    activation_policy: str = "NEXT_BAR"
    max_activation_bars: int = 5
    execution_buffer: float = 0.0
    stop_buffer: float = 0.0

    pattern_association_policy: str = "SAME_BAR (EXPERIMENTAL)"
    volume_observation_policy: str = "CONFLUENCE_CANDLE (EXPERIMENTAL)"
    fibonacci_status: str = "UNRESOLVED (Not Used in Candidate V1)"
    not_used_in_candidate_v1: bool = True

    target_r: float = 2.0
    intrabar_policy: str = "CONSERVATIVE / STOP_FIRST"

    source_commit: str = "05ae109eb1c631a8751e6ebf295fda032214f5e5"
    research_status: str = "ROBUST_CANDIDATE"

    limitations: Tuple[str, ...] = (
        "Backtest conduzido em dados OHLC históricos, não tick-by-tick;",
        "Modelagem de custos operacionais (spread/slippage) estimada em 0.03R;",
        "Monte Carlo conduzido por amostragem bootstrap de trades ativados;",
        "OOS pertencente ao mesmo universo histórico de 390.000 candles de pesquisa;",
        "Risco residual de data-snooping em simulações quantitativas;",
        "PatternAssociationPolicy.SAME_BAR mantida como experimental;",
        "VolumeObservationPolicy.CONFLUENCE_CANDLE mantida como experimental;",
        "Condição Fibonacci ainda não incorporada ao candidato V1 (UNRESOLVED);",
        "Performance quantitativa passada não garante resultados futuros.",
    )

    def compute_parameter_hash(self) -> str:
        """Gera um hash SHA-256 único e determinístico dos parâmetros congelados."""
        params_dict = {
            "candidate_id": self.candidate_id,
            "candidate_version": self.candidate_version,
            "strategy_id": self.strategy_id,
            "variant": self.variant,
            "exit_policy": self.exit_policy,
            "rsi_method": self.rsi_method,
            "rsi_period": self.rsi_period,
            "pivot_left": self.pivot_left,
            "pivot_right": self.pivot_right,
            "min_bars_between_pivots": self.min_bars_between_pivots,
            "max_bars_between_pivots": self.max_bars_between_pivots,
            "volume_min_relative": self.volume_min_relative,
            "activation_policy": self.activation_policy,
            "max_activation_bars": self.max_activation_bars,
            "execution_buffer": self.execution_buffer,
            "stop_buffer": self.stop_buffer,
            "pattern_association_policy": self.pattern_association_policy,
            "volume_observation_policy": self.volume_observation_policy,
            "fibonacci_status": self.fibonacci_status,
            "target_r": self.target_r,
            "intrabar_policy": self.intrabar_policy,
        }
        serialized = json.dumps(params_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def validate_immutability(self, expected_hash: str) -> bool:
        """Valida se os parâmetros não foram alterados silenciosamente."""
        return self.compute_parameter_hash() == expected_hash


# Instância congelada oficial do Candidato V1
HDF_ROBUST_CANDIDATE_V1 = RobustCandidateSpec()
HDF_CANDIDATE_V1_PARAMETER_HASH = HDF_ROBUST_CANDIDATE_V1.compute_parameter_hash()
