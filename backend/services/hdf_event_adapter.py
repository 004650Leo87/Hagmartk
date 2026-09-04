from __future__ import annotations

from typing import List, Optional

from backend.domain.candidate import HDF_ROBUST_CANDIDATE_V1
from backend.domain.market_events import EventFact, MarketEvent
from backend.domain.shadow_models import HDFEvidence
from backend.services.internal_event_engine import EvidenceObservation, InternalEventEngine
from backend.services.shadow_store import ShadowStoreRepository


class HDFRadarAdapter:
    evidence_key = "HDF_SHADOW_EVIDENCE_V1"

    @classmethod
    def to_observation(cls, evidence: HDFEvidence) -> EvidenceObservation:
        if evidence.is_test or evidence.source != "LIVE_PROSPECTIVE":
            raise ValueError("HDF RADAR accepts LIVE_PROSPECTIVE non-test evidence only")

        facts = (
            EventFact("hdf_stage", evidence.variant_stage, source="HDF"),
            EventFact("divergence_confirmed", evidence.divergence_confirmed, source="HDF"),
            EventFact("pivot_1_price", evidence.pivot_1_price, source="HDF", observed_at=evidence.pivot_1_time),
            EventFact("pivot_1_rsi", evidence.pivot_1_rsi, source="HDF", observed_at=evidence.pivot_1_time),
            EventFact("pivot_2_price", evidence.pivot_2_price, source="HDF", observed_at=evidence.pivot_2_time),
            EventFact("pivot_2_rsi", evidence.pivot_2_rsi, source="HDF", observed_at=evidence.pivot_2_time),
            EventFact("relative_volume", evidence.relative_volume, unit="x20avg", source="HDF"),
            EventFact("volume_pass", evidence.volume_pass, source="HDF"),
            EventFact("pattern_type", evidence.pattern_type, source="HDF"),
            EventFact("pattern_pass", evidence.pattern_pass, source="HDF"),
        )
        return EvidenceObservation(
            evidence_key=cls.evidence_key,
            evidence_id=evidence.evidence_id,
            strategy_id=HDF_ROBUST_CANDIDATE_V1.strategy_id,
            strategy_version=HDF_ROBUST_CANDIDATE_V1.candidate_version,
            asset=evidence.symbol,
            market=evidence.asset_class,
            timeframe=evidence.timeframe,
            detected_at=evidence.detected_at or evidence.created_at,
            direction=evidence.direction,
            trigger_facts=facts,
            assumptions=(
                "Shadow evidence only; no real-order execution.",
                "HDF stage is reported exactly as persisted and is not promoted by this adapter.",
            ),
            limitations=(
                "RADAR is an internal observation, not a Quant Event or trade recommendation.",
            ),
            metadata=(
                ("hdf_evidence_id", evidence.evidence_id),
                ("hdf_variant_stage", evidence.variant_stage),
                ("candidate_created", str(bool(evidence.candidate_created)).lower()),
                ("armed", str(bool(evidence.armed)).lower()),
                ("activated", str(bool(evidence.activated)).lower()),
            ),
        )

    @classmethod
    def build_radar(cls, evidence: HDFEvidence, engine: Optional[InternalEventEngine] = None) -> MarketEvent:
        event_engine = engine or InternalEventEngine()
        result = event_engine.build(cls.to_observation(evidence))
        if not result.accepted or result.event is None:
            raise ValueError(f"HDF RADAR build rejected: {result.reason_codes}")
        return result.event


class HDFRadarService:
    """Read-only adapter over persisted HDF shadow evidence."""

    def __init__(
        self,
        repository: Optional[ShadowStoreRepository] = None,
        engine: Optional[InternalEventEngine] = None,
    ) -> None:
        self.repository = repository or ShadowStoreRepository()
        self.engine = engine or InternalEventEngine()

    def list_live_radar(self, limit: int = 50) -> List[MarketEvent]:
        evidence_rows = self.repository.list_hdf_evidence(
            source="LIVE_PROSPECTIVE",
            is_test=False,
            limit=limit,
        )
        return [HDFRadarAdapter.build_radar(item, self.engine) for item in evidence_rows]
