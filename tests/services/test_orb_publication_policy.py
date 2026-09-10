from datetime import datetime, timedelta, timezone

from backend.services.orb_publication_policy import (
    OrbPublicationConfig,
    evaluate_orb_publication,
)

NOW = datetime(2026, 9, 9, 21, 0, tzinfo=timezone.utc)
CFG = OrbPublicationConfig(
    max_roots_per_window=3,
    window_minutes=15,
    symbol_cooldown_minutes=60,
    min_liquidity_percentile=70.0,
)


def _event(**changes):
    event = {
        "symbol": "BTCUSDT",
        "signal_id": "sig-1",
        "session_id": "session-1",
        "liquidity_percentile_24h": 95.0,
    }
    event.update(changes)
    return event


def _activity(minutes_ago, symbol="ETHUSDT", event_id="old", operation_key="ORB:old"):
    return {
        "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
        "symbol": symbol,
        "event_id": event_id,
        "operation_key": operation_key,
        "status": "PUBLISHED",
    }

def test_orb_publication_accepts_high_liquidity_when_budget_is_free():
    decision = evaluate_orb_publication(_event(), [], NOW, CFG)
    assert decision.allowed is True
    assert decision.reason == "QUALIFIED_FOR_PUBLICATION"
    assert decision.score == 95.0


def test_orb_publication_rejects_low_liquidity():
    decision = evaluate_orb_publication(
        _event(liquidity_percentile_24h=69.9), [], NOW, CFG,
    )
    assert decision.allowed is False
    assert decision.reason == "LIQUIDITY_BELOW_PUBLICATION_THRESHOLD"


def test_orb_publication_enforces_global_budget():
    recent = [_activity(2, event_id=f"past-{i}", operation_key=f"ORB:past-{i}") for i in range(3)]
    decision = evaluate_orb_publication(_event(), recent, NOW, CFG)
    assert decision.allowed is False
    assert decision.reason == "GLOBAL_PUBLICATION_BUDGET_EXCEEDED"


def test_orb_publication_enforces_symbol_cooldown():
    recent = [_activity(30, symbol="BTCUSDT")]
    decision = evaluate_orb_publication(_event(), recent, NOW, CFG)
    assert decision.allowed is False
    assert decision.reason == "SYMBOL_COOLDOWN_ACTIVE"


def test_orb_publication_rejects_duplicate_signal_or_session():
    by_signal = [_activity(30, event_id="sig-1")]
    assert evaluate_orb_publication(_event(), by_signal, NOW, CFG).reason == "DUPLICATE_SIGNAL_ID"
    by_session = [_activity(30, operation_key="ORB:session-1")]
    assert evaluate_orb_publication(_event(), by_session, NOW, CFG).reason == "DUPLICATE_SESSION"
