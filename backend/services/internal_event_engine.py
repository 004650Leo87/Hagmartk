from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Optional, Tuple

from backend.domain.evidence_contracts import EvidenceContractRegistry, build_product_evidence_registry
from backend.domain.market_events import (
    EventFact,
    EventStatistic,
    MarketEvent,
    MarketEventClass,
    MarketEventState,
)
from backend.domain.strategy_contracts import StrategyContractRegistry, build_product_strategy_registry


@dataclass(frozen=True)
class EvidenceObservation:
    evidence_key: str
    evidence_id: str
    strategy_id: str
    strategy_version: str
    asset: str
    market: str
    timeframe: str
    detected_at: str
    time_domain: str = "UTC"
    direction: str = ""
    confirmed_at: str = ""
    trigger_facts: Tuple[EventFact, ...] = field(default_factory=tuple)
    reference_region: Optional[Tuple[float, float]] = None
    invalidation_level: Optional[float] = None
    objective_regions: Tuple[Tuple[float, float], ...] = field(default_factory=tuple)
    statistics: Tuple[EventStatistic, ...] = field(default_factory=tuple)
    sample_size: Optional[int] = None
    evaluation_window: str = ""
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EventBuildResult:
    accepted: bool
    event: Optional[MarketEvent]
    reason_codes: Tuple[str, ...]


class InternalEventEngine:
    """Pure internal evidence -> MarketEvent transformer. No publishing or trading."""

    external_publication_enabled = False
    real_order_execution_enabled = False
    quant_event_promotion_enabled = False

    def __init__(
        self,
        strategies: Optional[StrategyContractRegistry] = None,
        evidence: Optional[EvidenceContractRegistry] = None,
    ) -> None:
        self.strategies = strategies or build_product_strategy_registry()
        self.evidence = evidence or build_product_evidence_registry()

    @staticmethod
    def _event_id(observation: EvidenceObservation, event_class: MarketEventClass) -> str:
        raw = "|".join([
            observation.evidence_key,
            observation.evidence_id,
            observation.strategy_id,
            observation.strategy_version,
            event_class.value,
        ])
        return "mktevt_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @staticmethod
    def _default_event_class(evidence_contract) -> MarketEventClass:
        if evidence_contract.research_only:
            return MarketEventClass.RESEARCH_UPDATE
        if evidence_contract.can_support_quant_event:
            return MarketEventClass.RADAR
        return MarketEventClass.RESEARCH_UPDATE

    def build(
        self,
        observation: EvidenceObservation,
        requested_class: Optional[MarketEventClass] = None,
    ) -> EventBuildResult:
        evidence_contract = self.evidence.get(observation.evidence_key)
        if evidence_contract is None:
            return EventBuildResult(False, None, ("EVIDENCE_NOT_REGISTERED",))

        strategy = self.strategies.get(observation.strategy_id, observation.strategy_version)
        if strategy is None:
            return EventBuildResult(False, None, ("STRATEGY_NOT_REGISTERED",))

        if (
            evidence_contract.strategy_id != observation.strategy_id
            or evidence_contract.strategy_version != observation.strategy_version
        ):
            return EventBuildResult(False, None, ("EVIDENCE_STRATEGY_MISMATCH",))

        event_class = requested_class or self._default_event_class(evidence_contract)
        if event_class not in strategy.allowed_event_classes:
            return EventBuildResult(False, None, ("EVENT_CLASS_NOT_ALLOWED_BY_STRATEGY",))

        if event_class == MarketEventClass.QUANT_EVENT:
            return EventBuildResult(False, None, ("QUANT_EVENT_PROMOTION_NOT_ENABLED_IN_ENGINE_V1",))

        publication_reasons = (
            "INTERNAL_EVENT_ONLY",
            "EXTERNAL_PUBLICATION_DISABLED",
            "QUANT_GATE_NOT_EVALUATED",
        )
        metadata = (
            ("evidence_key", observation.evidence_key),
            ("evidence_id", observation.evidence_id),
            *observation.metadata,
        )
        event = MarketEvent(
            event_id=self._event_id(observation, event_class),
            event_class=event_class,
            state=MarketEventState.DETECTED,
            asset=observation.asset,
            market=observation.market,
            timeframe=observation.timeframe,
            detected_at=observation.detected_at,
            time_domain=observation.time_domain,
            strategy_id=observation.strategy_id,
            strategy_version=observation.strategy_version,
            confirmed_at=observation.confirmed_at,
            direction=observation.direction,
            trigger_facts=observation.trigger_facts,
            reference_region=observation.reference_region,
            invalidation_level=observation.invalidation_level,
            objective_regions=(),
            provenance=evidence_contract.provenance,
            statistics=observation.statistics,
            sample_size=observation.sample_size,
            evaluation_window=observation.evaluation_window,
            assumptions=observation.assumptions,
            limitations=tuple(observation.limitations) + tuple(evidence_contract.limitations),
            publication_eligible=False,
            publication_reasons=publication_reasons,
            metadata=metadata,
        )

        schema_errors = event.schema_errors()
        if schema_errors:
            return EventBuildResult(
                False,
                None,
                ("EVENT_SCHEMA_INVALID", *schema_errors),
            )

        return EventBuildResult(
            True,
            event,
            ("INTERNAL_EVENT_CREATED", event_class.value),
        )
