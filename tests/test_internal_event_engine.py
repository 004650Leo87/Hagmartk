from backend.domain.market_events import EventFact, MarketEventClass
from backend.services.internal_event_engine import EvidenceObservation, InternalEventEngine


def hdf_observation(**overrides):
    payload = dict(
        evidence_key="HDF_SHADOW_EVIDENCE_V1",
        evidence_id="ev_001",
        strategy_id="hagmartk_divergence_flow",
        strategy_version="1.0.0",
        asset="EURUSD",
        market="FOREX",
        timeframe="H1",
        detected_at="2026-09-04T02:00:00+00:00",
        direction="BULLISH",
        trigger_facts=(
            EventFact("divergence", "regular_bullish", source="HDF"),
            EventFact("volume_relative", 1.2, unit="x20avg", source="HDF"),
        ),
        reference_region=(1.1000, 1.1010),
        invalidation_level=1.0950,
        objective_regions=((1.1100, 1.1110),),
        limitations=("Shadow evidence only",),
    )
    payload.update(overrides)
    return EvidenceObservation(**payload)


def test_hdf_shadow_evidence_defaults_to_internal_radar():
    engine = InternalEventEngine()
    result = engine.build(hdf_observation())
    assert result.accepted is True
    assert result.event is not None
    assert result.event.event_class == MarketEventClass.RADAR
    assert result.event.publication_eligible is False
    assert result.event.objective_regions == ()
    assert result.event.schema_errors() == ()
    assert engine.external_publication_enabled is False
    assert engine.real_order_execution_enabled is False


def test_fibonacci_research_defaults_to_research_update():
    observation = hdf_observation(
        evidence_key="HDF_FIBONACCI_RESEARCH_V1",
        evidence_id="fib_001",
        reference_region=None,
        invalidation_level=None,
        objective_regions=(),
    )
    result = InternalEventEngine().build(observation)
    assert result.accepted is True
    assert result.event is not None
    assert result.event.event_class == MarketEventClass.RESEARCH_UPDATE
    assert result.event.publication_eligible is False


def test_cycle_theory_fidelity_defaults_to_research_update():
    observation = EvidenceObservation(
        evidence_key="CYCLE_THEORY_V111_FIDELITY_EVIDENCE",
        evidence_id="gate_3z",
        strategy_id="cycle_theory_v111_fidelity",
        strategy_version="111.00",
        asset="XAUUSD",
        market="METALS",
        timeframe="M15",
        detected_at="2026-09-04T02:00:00+00:00",
        trigger_facts=(EventFact("gate", "PARTIAL", source="PARITY_MATRIX"),),
    )
    result = InternalEventEngine().build(observation)
    assert result.accepted is True
    assert result.event is not None
    assert result.event.event_class == MarketEventClass.RESEARCH_UPDATE


def test_quant_event_request_is_explicitly_blocked_in_engine_v1():
    result = InternalEventEngine().build(
        hdf_observation(),
        requested_class=MarketEventClass.QUANT_EVENT,
    )
    assert result.accepted is False
    assert result.event is None
    assert result.reason_codes == ("QUANT_EVENT_PROMOTION_NOT_ENABLED_IN_ENGINE_V1",)


def test_unknown_evidence_is_rejected():
    observation = hdf_observation(evidence_key="UNKNOWN_EVIDENCE")
    result = InternalEventEngine().build(observation)
    assert result.accepted is False
    assert result.reason_codes == ("EVIDENCE_NOT_REGISTERED",)


def test_evidence_strategy_mismatch_is_rejected():
    observation = hdf_observation(
        strategy_id="cycle_theory_v111_fidelity",
        strategy_version="111.00",
    )
    result = InternalEventEngine().build(observation)
    assert result.accepted is False
    assert result.reason_codes == ("EVIDENCE_STRATEGY_MISMATCH",)


def test_event_id_is_deterministic_for_same_evidence_and_class():
    engine = InternalEventEngine()
    first = engine.build(hdf_observation())
    second = engine.build(hdf_observation())
    assert first.event is not None and second.event is not None
    assert first.event.event_id == second.event.event_id
