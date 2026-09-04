from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH


class ShadowState(str, Enum):
    DETECTED = "DETECTED"
    DIVERGENCE_CONFIRMED = "DIVERGENCE_CONFIRMED"
    CONFLUENCE_COMPLETE = "CONFLUENCE_COMPLETE"
    ARMED = "ARMED"
    BOOTSTRAP_EXISTING = "BOOTSTRAP_EXISTING"
    ACTIVATED = "ACTIVATED"
    TARGET_2R = "TARGET_2R"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


class ScannerStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_NEW_CANDLE = "WAITING_NEW_CANDLE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"
    RECOVERING = "RECOVERING"


class ShadowEventType(str, Enum):
    SETUP_DETECTED = "SETUP_DETECTED"
    CONFLUENCE_CONFIRMED = "CONFLUENCE_CONFIRMED"
    SETUP_ARMED = "SETUP_ARMED"
    ENTRY_ACTIVATED = "ENTRY_ACTIVATED"
    MILESTONE_1R = "MILESTONE_1R"
    TARGET_REACHED = "TARGET_REACHED"
    STOP_REACHED = "STOP_REACHED"
    SETUP_EXPIRED = "SETUP_EXPIRED"
    SETUP_INVALIDATED = "SETUP_INVALIDATED"


@dataclass
class HDFEvidence:
    evidence_id: str
    symbol: str
    timeframe: str
    asset_class: str
    direction: str  # BULLISH or BEARISH

    pivot_1_time: str
    pivot_1_price: float
    pivot_1_rsi: float

    pivot_2_time: str
    pivot_2_price: float
    pivot_2_rsi: float

    divergence_confirmed: bool = True
    relative_volume: float = 0.0
    volume_pass: bool = False

    pattern_type: str = "NONE"
    pattern_pass: bool = False
    pattern_policy: str = "SAME_BAR"

    variant_stage: str = "HDF_D"  # HDF_D, HDF_DV, HDF_DP, HDF_DVP
    candidate_created: bool = False
    armed: bool = False
    activated: bool = False

    event_id: Optional[str] = None  # nullable link to shadow_events
    reason_codes: List[str] = field(default_factory=list)

    source: str = "LIVE_PROSPECTIVE"  # LIVE_PROSPECTIVE | HISTORICAL_BACKFILL | TEST | DEMO
    is_test: bool = False  # False for live/shadow evidence, True for test fixtures
    detected_at: str = ""
    created_at: str = ""


@dataclass
class EvidencePayload:
    symbol: str
    timeframe: str
    direction: str
    candles_reference_range: List[Dict[str, Any]] = field(default_factory=list)
    pivot1: Dict[str, Any] = field(default_factory=dict)
    pivot2: Dict[str, Any] = field(default_factory=dict)
    rsi1: float = 0.0
    rsi2: float = 0.0
    divergence_price_line: Tuple[float, float] = (0.0, 0.0)
    divergence_rsi_line: Tuple[float, float] = (0.0, 0.0)
    pattern_candle: Dict[str, Any] = field(default_factory=dict)
    volume_relative: float = 0.0
    activation_level: float = 0.0
    entry_price: float = 0.0
    initial_stop: float = 0.0
    target_price: float = 0.0
    watermark_text: str = ""

    def __post_init__(self):
        if not self.watermark_text:
            self.watermark_text = f"{self.symbol} • {self.timeframe}"


@dataclass
class ShadowTransition:
    transition_id: str
    event_id: str
    from_state: str
    to_state: str
    timestamp: str
    candle_timestamp: str
    market_price: float
    reason: str


@dataclass
class ShadowEvent:
    event_id: str
    candidate_id: str = "hdf_dvp_exit_2r"
    candidate_version: str = "1.0.0"
    parameter_hash: str = HDF_CANDIDATE_V1_PARAMETER_HASH

    symbol: str = "EURUSD"
    asset_class: str = "FOREX"
    timeframe: str = "H1"
    direction: str = "BULLISH"
    pattern_type: str = "BULLISH_ENGULFING"

    pivot_1_time: str = ""
    pivot_1_price: float = 0.0
    pivot_1_rsi: float = 0.0

    pivot_2_time: str = ""
    pivot_2_price: float = 0.0
    pivot_2_rsi: float = 0.0

    divergence_confirmed_at: str = ""
    relative_volume: float = 1.0
    volume_source: str = "TICK_VOLUME"

    confluence_time: str = ""
    armed_at: str = ""
    activation_level: float = 0.0

    activated_at: str = ""
    entry_price: float = 0.0
    initial_stop: float = 0.0
    target_2R: float = 0.0
    initial_risk: float = 0.0

    current_state: str = "ARMED"
    milestone_1r_reached: bool = False

    mfe_r_live: float = 0.0
    mae_r_live: float = 0.0
    bars_since_activation: int = 0

    market_source: str = "OHLCDataCache / MT5"
    broker: str = "MetaTrader 5"

    market_candle_time: str = ""
    received_at: str = ""
    processed_at: str = ""

    created_at: str = ""
    updated_at: str = ""

    metadata: Dict[str, Any] = field(default_factory=dict)
    evidence: Optional[Dict[str, Any]] = None

    def compute_deduplication_key(self, event_type: str) -> str:
        """Chave única para impedir duplicação acidental por restart ou reprocessamento."""
        return f"{self.candidate_version}_{self.symbol}_{self.timeframe}_{self.confluence_time}_{event_type}"


@dataclass
class ShadowScannerState:
    candidate_id: str
    symbol: str
    timeframe: str
    enabled: bool = True
    last_processed_candle: str = ""
    last_scan_at: str = ""
    scanner_status: str = "RUNNING"
    error_message: str = ""
    scan_cycle_count_total: int = 0
    evaluation_count_total: int = 0
    last_evaluated_candle_time: str = ""
    last_evaluation_at: str = ""
    last_result_stage: str = "NONE"


@dataclass
class ShadowStatistics:
    shadow_started_at: str = ""
    total_events_detected: int = 0
    confluences_count: int = 0
    armed_count: int = 0
    activated_count: int = 0
    targets_reached_count: int = 0
    stops_reached_count: int = 0
    expired_count: int = 0
    invalidated_count: int = 0
    open_count: int = 0

    win_rate_shadow: float = 0.0
    net_r_shadow: float = 0.0
    expectancy_r_shadow: float = 0.0
    profit_factor_shadow: float = 0.0
    max_drawdown_r_shadow: float = 0.0

    mfe_median_r: float = 0.0
    mae_median_r: float = 0.0
    average_holding_bars: float = 0.0

    events_per_week: float = 0.0
    events_per_month: float = 0.0
