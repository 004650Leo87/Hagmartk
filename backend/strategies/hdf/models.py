from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import pandas as pd


class HDFState(Enum):
    DETECTED = "DETECTED"
    DIVERGENCE_CONFIRMED = "DIVERGENCE_CONFIRMED"
    CONFLUENCE_PARTIAL = "CONFLUENCE_PARTIAL"
    CONFLUENCE_COMPLETE = "CONFLUENCE_COMPLETE"
    ARMED = "ARMED"
    ACTIVATED = "ACTIVATED"
    INVALIDATED_BEFORE_ACTIVATION = "INVALIDATED_BEFORE_ACTIVATION"
    EXPIRED = "EXPIRED"
    TARGET_1 = "TARGET_1"
    TARGET_2 = "TARGET_2"
    TARGET_3 = "TARGET_3"
    STOPPED = "STOPPED"


# Aliases legados para compatibilidade
DIVAPState = HDFState


class ForexSession(Enum):
    ASIA = "ASIA"                      # 00:00 - 08:00 UTC
    LONDON = "LONDON"                  # 08:00 - 16:00 UTC
    NEW_YORK = "NEW_YORK"              # 13:00 - 21:00 UTC
    LONDON_NEW_YORK_OVERLAP = "OVERLAP"# 13:00 - 16:00 UTC
    OTHER = "OTHER"                    # 21:00 - 24:00 UTC


def classify_forex_session_utc(timestamp_str: str) -> ForexSession:
    """Classifica a sessão Forex com base no horário UTC explícito."""
    try:
        dt = pd.to_datetime(timestamp_str, utc=True)
        h = dt.hour
        if 13 <= h < 16:
            return ForexSession.LONDON_NEW_YORK_OVERLAP
        elif 8 <= h < 13:
            return ForexSession.LONDON
        elif 16 <= h < 21:
            return ForexSession.NEW_YORK
        elif 0 <= h < 8:
            return ForexSession.ASIA
        else:
            return ForexSession.OTHER
    except Exception:
        return ForexSession.OTHER


class PivotEqualityPolicy(Enum):
    STRICT = "STRICT"
    ALLOW_EQUAL = "ALLOW_EQUAL"


class VolumeSource(Enum):
    REAL_VOLUME = "REAL_VOLUME"
    TICK_VOLUME = "TICK_VOLUME"
    EXCHANGE_VOLUME = "EXCHANGE_VOLUME"
    UNKNOWN = "UNKNOWN"


class ReversalPatternType(Enum):
    NONE = "NONE"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    HAMMER = "HAMMER"
    SHOOTING_STAR = "SHOOTING_STAR"


@dataclass
class HDFTemporalModel:
    pivot_1_time: str = ""
    pivot_2_time: str = ""
    pivot_1_confirmed_at: str = ""
    pivot_2_confirmed_at: str = ""
    divergence_detected_at: str = ""
    divergence_confirmed_at: str = ""
    volume_observed_at: str = ""
    fib_condition_known_at: str = ""
    reversal_pattern_time: str = ""
    reversal_pattern_confirmed_at: str = ""
    confluence_completed_at: str = ""
    armed_at: str = ""
    activation_time: str = ""
    entry_at: str = ""
    data_available_at_decision: str = ""


DIVAPTemporalModel = HDFTemporalModel


@dataclass
class FibonacciAnchorPolicy:
    """Interface para política de ancoragem Fibonacci (marcada como UNRESOLVED na documentação)."""

    policy_id: str = "UNRESOLVED_DEFAULT"
    description: str = "Seleção de ancoras de Fibonacci pendente de especificação documental inequívoca."
    is_resolved: bool = False
    fibonacci_specification_status: str = "UNRESOLVED"
    anchor_A_type: str = "UNRESOLVED"
    anchor_B_type: str = "UNRESOLVED"
    levels: List[float] = field(default_factory=lambda: [0.618, 1.000, 1.618, 2.000, 2.618])


@dataclass
class HDFOccurrence:
    occurrence_id: str
    symbol: str
    timeframe: str
    direction: str  # "BULLISH" ou "BEARISH"
    state: HDFState
    temporal_model: HDFTemporalModel
    variant: str  # "HDF_D", "HDF_DV", "HDF_DP", "HDF_DVP", "HDF_DAFP"

    # Preços e pivôs
    price_p1: float = 0.0
    price_p2: float = 0.0
    rsi_p1: float = 0.0
    rsi_p2: float = 0.0
    price_delta: float = 0.0
    price_delta_pct: float = 0.0
    rsi_delta: float = 0.0
    bars_between_pivots: int = 0
    rsi_extreme_class: str = "NEUTRAL"

    # Volume
    volume_current: float = 0.0
    volume_ma20: float = 0.0
    relative_volume: float = 0.0
    relative_volume_bucket: str = "<1.0"
    volume_source: VolumeSource = VolumeSource.TICK_VOLUME

    # Padrão de reversão
    pattern_type: ReversalPatternType = ReversalPatternType.NONE
    pattern_high: float = 0.0
    pattern_low: float = 0.0
    pattern_strength_features: Dict[str, Any] = field(default_factory=dict)

    # Níveis de armação, ativação e risco
    activation_level: float = 0.0
    entry_price: float = 0.0
    initial_stop: float = 0.0
    initial_risk: float = 0.0
    stop_buffer: float = 0.0
    bars_to_activation: Optional[int] = None
    activation_policy: str = "NEXT_BAR"

    # Fibonacci (UNRESOLVED)
    fib_policy: FibonacciAnchorPolicy = field(default_factory=FibonacciAnchorPolicy)

    # Sessão e contexto
    session: ForexSession = ForexSession.OTHER

    # Excursões MFE/MAE somente pós-entrada (entry_at)
    mfe_price: float = 0.0
    mae_price: float = 0.0
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    bars_to_mfe: int = 0
    bars_to_mae: int = 0
    excursions_windows: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Metadados e rastro
    metadata: Dict[str, Any] = field(default_factory=dict)


DIVAPOccurrence = HDFOccurrence
