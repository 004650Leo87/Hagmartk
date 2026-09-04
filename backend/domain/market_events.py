from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple


SHORT_PUBLIC_DISCLAIMER = (
    "Evento quantitativo para estudo e acompanhamento. "
    "Não constitui recomendação individual de investimento."
)


class MarketEventClass(str, Enum):
    MARKET_BRIEF = "MARKET_BRIEF"
    RADAR = "RADAR"
    QUANT_EVENT = "QUANT_EVENT"
    EVENT_UPDATE = "EVENT_UPDATE"
    EVENT_AUTOPSY = "EVENT_AUTOPSY"
    RESEARCH_UPDATE = "RESEARCH_UPDATE"
    SYSTEM_STATUS = "SYSTEM_STATUS"


class MarketEventState(str, Enum):
    DETECTED = "DETECTED"
    FORMING = "FORMING"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"


class TerminalReason(str, Enum):
    TARGET_REACHED = "TARGET_REACHED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    DATA_INVALID = "DATA_INVALID"


class EvidenceProvenance(str, Enum):
    LIVE = "LIVE"
    SHADOW = "SHADOW"
    BACKTEST = "BACKTEST"
    RESEARCH = "RESEARCH"


@dataclass(frozen=True)
class EventFact:
    name: str
    value: Any
    unit: str = ""
    source: str = ""
    observed_at: str = ""


@dataclass(frozen=True)
class EventStatistic:
    name: str
    value: float
    denominator: int
    provenance: EvidenceProvenance
    window: str


@dataclass(frozen=True)
class MarketEvent:
    event_id: str
    event_class: MarketEventClass
    state: MarketEventState
    asset: str
    market: str
    timeframe: str
    detected_at: str
    time_domain: str
    strategy_id: str = ""
    strategy_version: str = ""
    confirmed_at: str = ""
    direction: str = ""
    trigger_facts: Tuple[EventFact, ...] = field(default_factory=tuple)
    reference_region: Optional[Tuple[float, float]] = None
    invalidation_level: Optional[float] = None
    objective_regions: Tuple[Tuple[float, float], ...] = field(default_factory=tuple)
    provenance: EvidenceProvenance = EvidenceProvenance.RESEARCH
    statistics: Tuple[EventStatistic, ...] = field(default_factory=tuple)
    sample_size: Optional[int] = None
    evaluation_window: str = ""
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    publication_eligible: bool = False
    publication_reasons: Tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = SHORT_PUBLIC_DISCLAIMER
    terminal_reason: Optional[TerminalReason] = None
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)

    def schema_errors(self) -> Tuple[str, ...]:
        errors = []
        for name, value in (
            ("event_id", self.event_id),
            ("asset", self.asset),
            ("market", self.market),
            ("timeframe", self.timeframe),
            ("detected_at", self.detected_at),
            ("time_domain", self.time_domain),
        ):
            if not str(value).strip():
                errors.append(f"MISSING_{name.upper()}")

        if self.state == MarketEventState.RESOLVED and self.terminal_reason is None:
            errors.append("RESOLVED_WITHOUT_TERMINAL_REASON")
        if self.state != MarketEventState.RESOLVED and self.terminal_reason is not None:
            errors.append("TERMINAL_REASON_BEFORE_RESOLVED")

        complete_trade_structure = (
            self.reference_region is not None
            and self.invalidation_level is not None
            and bool(self.objective_regions)
        )
        if self.event_class != MarketEventClass.QUANT_EVENT and complete_trade_structure:
            errors.append("COMPLETE_TRADE_STRUCTURE_REQUIRES_QUANT_EVENT")

        if self.reference_region is not None and self.reference_region[0] > self.reference_region[1]:
            errors.append("REFERENCE_REGION_REVERSED")

        for stat in self.statistics:
            if stat.denominator <= 0:
                errors.append(f"STAT_DENOMINATOR_INVALID:{stat.name}")
            if not stat.window.strip():
                errors.append(f"STAT_WINDOW_MISSING:{stat.name}")

        if self.event_class == MarketEventClass.QUANT_EVENT:
            if not self.strategy_id.strip():
                errors.append("QUANT_MISSING_STRATEGY_ID")
            if not self.strategy_version.strip():
                errors.append("QUANT_MISSING_STRATEGY_VERSION")
            if not self.confirmed_at.strip():
                errors.append("QUANT_MISSING_CONFIRMED_AT")
            if not self.trigger_facts:
                errors.append("QUANT_MISSING_TRIGGER_FACTS")
            if self.reference_region is None:
                errors.append("QUANT_MISSING_REFERENCE_REGION")
            if self.invalidation_level is None:
                errors.append("QUANT_MISSING_INVALIDATION")
            if not self.limitations:
                errors.append("QUANT_MISSING_LIMITATIONS")
            if not self.publication_reasons:
                errors.append("QUANT_MISSING_PUBLICATION_REASON")
            if not self.disclaimer.strip():
                errors.append("QUANT_MISSING_DISCLAIMER")

            if self.statistics:
                if self.sample_size is None or self.sample_size <= 0:
                    errors.append("QUANT_STATS_MISSING_SAMPLE_SIZE")
                if not self.evaluation_window.strip():
                    errors.append("QUANT_STATS_MISSING_EVALUATION_WINDOW")
                if not self.assumptions:
                    errors.append("QUANT_STATS_MISSING_ASSUMPTIONS")

        return tuple(errors)

    def is_publishable_quant_event(self) -> bool:
        return (
            self.event_class == MarketEventClass.QUANT_EVENT
            and self.publication_eligible
            and not self.schema_errors()
        )


@dataclass(frozen=True)
class EventTransition:
    event_id: str
    from_state: MarketEventState
    to_state: MarketEventState
    timestamp: str
    reason: str
    terminal_reason: Optional[TerminalReason] = None


_ALLOWED_NEXT = {
    MarketEventState.DETECTED: MarketEventState.FORMING,
    MarketEventState.FORMING: MarketEventState.CONFIRMED,
    MarketEventState.CONFIRMED: MarketEventState.ACTIVE,
    MarketEventState.ACTIVE: MarketEventState.RESOLVED,
}


def validate_transition(event: MarketEvent, transition: EventTransition) -> Tuple[str, ...]:
    errors = []
    if transition.event_id != event.event_id:
        errors.append("EVENT_ID_MISMATCH")
    if transition.from_state != event.state:
        errors.append("FROM_STATE_MISMATCH")
    expected = _ALLOWED_NEXT.get(event.state)
    if expected is None or transition.to_state != expected:
        errors.append("INVALID_LIFECYCLE_TRANSITION")
    if not transition.timestamp.strip():
        errors.append("TRANSITION_TIMESTAMP_MISSING")
    if not transition.reason.strip():
        errors.append("TRANSITION_REASON_MISSING")

    if transition.to_state == MarketEventState.RESOLVED:
        if transition.terminal_reason is None:
            errors.append("RESOLUTION_TERMINAL_REASON_MISSING")
    elif transition.terminal_reason is not None:
        errors.append("TERMINAL_REASON_ON_NON_RESOLUTION")

    return tuple(errors)


def market_event_to_dict(event: MarketEvent) -> Dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_class": event.event_class.value,
        "state": event.state.value,
        "asset": event.asset,
        "market": event.market,
        "timeframe": event.timeframe,
        "detected_at": event.detected_at,
        "time_domain": event.time_domain,
        "strategy_id": event.strategy_id,
        "strategy_version": event.strategy_version,
        "confirmed_at": event.confirmed_at,
        "direction": event.direction,
        "trigger_facts": [
            {
                "name": fact.name,
                "value": fact.value,
                "unit": fact.unit,
                "source": fact.source,
                "observed_at": fact.observed_at,
            }
            for fact in event.trigger_facts
        ],
        "reference_region": list(event.reference_region) if event.reference_region else None,
        "invalidation_level": event.invalidation_level,
        "objective_regions": [list(region) for region in event.objective_regions],
        "provenance": event.provenance.value,
        "statistics": [
            {
                "name": stat.name,
                "value": stat.value,
                "denominator": stat.denominator,
                "provenance": stat.provenance.value,
                "window": stat.window,
            }
            for stat in event.statistics
        ],
        "sample_size": event.sample_size,
        "evaluation_window": event.evaluation_window,
        "assumptions": list(event.assumptions),
        "limitations": list(event.limitations),
        "publication_eligible": event.publication_eligible,
        "publication_reasons": list(event.publication_reasons),
        "disclaimer": event.disclaimer,
        "terminal_reason": event.terminal_reason.value if event.terminal_reason else None,
        "metadata": dict(event.metadata),
    }


def transition_to_dict(transition: EventTransition) -> Dict[str, Any]:
    return {
        "event_id": transition.event_id,
        "from_state": transition.from_state.value,
        "to_state": transition.to_state.value,
        "timestamp": transition.timestamp,
        "reason": transition.reason,
        "terminal_reason": transition.terminal_reason.value if transition.terminal_reason else None,
    }
