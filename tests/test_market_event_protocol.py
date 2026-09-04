from dataclasses import FrozenInstanceError

import pytest

from backend.domain.market_events import (
    EventFact,
    EventStatistic,
    EvidenceProvenance,
    EventTransition,
    MarketEvent,
    MarketEventClass,
    MarketEventState,
    TerminalReason,
    validate_transition,
)


def make_valid_quant(**overrides):
    payload = dict(
        event_id="evt_quant_001",
        event_class=MarketEventClass.QUANT_EVENT,
        state=MarketEventState.CONFIRMED,
        asset="EURUSD",
        market="FOREX",
        timeframe="H1",
        detected_at="2026-09-04T02:00:00+00:00",
        time_domain="UTC",
        strategy_id="hdf_dvp_exit_2r",
        strategy_version="1.0.0",
        confirmed_at="2026-09-04T02:00:00+00:00",
        trigger_facts=(
            EventFact("divergence", "regular_bullish", source="HDF", observed_at="2026-09-04T02:00:00+00:00"),
            EventFact("volume_relative", 1.24, unit="x20avg", source="HDF"),
        ),
        reference_region=(1.1000, 1.1010),
        invalidation_level=1.0950,
        objective_regions=((1.1100, 1.1110),),
        provenance=EvidenceProvenance.SHADOW,
        limitations=("Shadow observation only",),
        publication_eligible=True,
        publication_reasons=("GATE_PASSED",),
    )
    payload.update(overrides)
    return MarketEvent(**payload)


def test_valid_quant_event_is_publishable():
    event = make_valid_quant()
    assert event.schema_errors() == ()
    assert event.is_publishable_quant_event() is True


def test_quant_event_missing_required_contract_is_blocked():
    event = make_valid_quant(
        strategy_id="",
        confirmed_at="",
        trigger_facts=(),
        reference_region=None,
        limitations=(),
        publication_reasons=(),
    )
    errors = set(event.schema_errors())
    assert "QUANT_MISSING_STRATEGY_ID" in errors
    assert "QUANT_MISSING_CONFIRMED_AT" in errors
    assert "QUANT_MISSING_TRIGGER_FACTS" in errors
    assert "QUANT_MISSING_REFERENCE_REGION" in errors
    assert "QUANT_MISSING_LIMITATIONS" in errors
    assert "QUANT_MISSING_PUBLICATION_REASON" in errors
    assert event.is_publishable_quant_event() is False


def test_statistics_require_denominator_window_and_quant_context():
    stat = EventStatistic(
        name="hit_rate",
        value=0.61,
        denominator=184,
        provenance=EvidenceProvenance.BACKTEST,
        window="2025-01-01/2026-01-01",
    )
    event = make_valid_quant(
        statistics=(stat,),
        sample_size=184,
        evaluation_window="2025-01-01/2026-01-01",
        assumptions=("OHLC backtest; costs modeled separately",),
    )
    assert event.schema_errors() == ()


def test_statistics_without_sample_context_are_blocked():
    stat = EventStatistic(
        name="expectancy_r",
        value=0.1,
        denominator=20,
        provenance=EvidenceProvenance.SHADOW,
        window="rolling",
    )
    event = make_valid_quant(statistics=(stat,), sample_size=None, evaluation_window="", assumptions=())
    errors = set(event.schema_errors())
    assert "QUANT_STATS_MISSING_SAMPLE_SIZE" in errors
    assert "QUANT_STATS_MISSING_EVALUATION_WINDOW" in errors
    assert "QUANT_STATS_MISSING_ASSUMPTIONS" in errors


def test_non_quant_event_cannot_impersonate_complete_trade_structure():
    event = make_valid_quant(event_class=MarketEventClass.RADAR, strategy_id="", strategy_version="")
    assert "COMPLETE_TRADE_STRUCTURE_REQUIRES_QUANT_EVENT" in event.schema_errors()


def test_market_event_is_immutable():
    event = make_valid_quant()
    with pytest.raises(FrozenInstanceError):
        event.asset = "GBPUSD"


def test_canonical_lifecycle_transition_is_accepted():
    event = make_valid_quant(state=MarketEventState.DETECTED, publication_eligible=False)
    transition = EventTransition(
        event_id=event.event_id,
        from_state=MarketEventState.DETECTED,
        to_state=MarketEventState.FORMING,
        timestamp="2026-09-04T02:01:00+00:00",
        reason="CONDITIONS_STILL_FORMING",
    )
    assert validate_transition(event, transition) == ()


def test_lifecycle_skip_is_rejected():
    event = make_valid_quant(state=MarketEventState.DETECTED, publication_eligible=False)
    transition = EventTransition(
        event_id=event.event_id,
        from_state=MarketEventState.DETECTED,
        to_state=MarketEventState.ACTIVE,
        timestamp="2026-09-04T02:01:00+00:00",
        reason="INVALID_SKIP",
    )
    assert "INVALID_LIFECYCLE_TRANSITION" in validate_transition(event, transition)


def test_resolution_requires_terminal_reason():
    event = make_valid_quant(state=MarketEventState.ACTIVE)
    transition = EventTransition(
        event_id=event.event_id,
        from_state=MarketEventState.ACTIVE,
        to_state=MarketEventState.RESOLVED,
        timestamp="2026-09-04T03:00:00+00:00",
        reason="EVENT_TERMINATED",
    )
    assert "RESOLUTION_TERMINAL_REASON_MISSING" in validate_transition(event, transition)


def test_resolution_with_terminal_reason_is_accepted():
    event = make_valid_quant(state=MarketEventState.ACTIVE)
    transition = EventTransition(
        event_id=event.event_id,
        from_state=MarketEventState.ACTIVE,
        to_state=MarketEventState.RESOLVED,
        timestamp="2026-09-04T03:00:00+00:00",
        reason="TARGET_OBSERVED",
        terminal_reason=TerminalReason.TARGET_REACHED,
    )
    assert validate_transition(event, transition) == ()


def test_market_event_serialization_is_json_safe():
    import json
    from backend.domain.market_events import market_event_to_dict, transition_to_dict

    event = make_valid_quant()
    payload = market_event_to_dict(event)
    assert payload["event_class"] == "QUANT_EVENT"
    assert payload["state"] == "CONFIRMED"
    assert payload["provenance"] == "SHADOW"
    json.dumps(payload)

    transition = EventTransition(
        event_id=event.event_id,
        from_state=MarketEventState.CONFIRMED,
        to_state=MarketEventState.ACTIVE,
        timestamp="2026-09-04T02:05:00+00:00",
        reason="ACTIVATION_CONFIRMED",
    )
    t_payload = transition_to_dict(transition)
    assert t_payload["from_state"] == "CONFIRMED"
    assert t_payload["to_state"] == "ACTIVE"
    json.dumps(t_payload)
