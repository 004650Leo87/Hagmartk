from datetime import datetime, timezone

from backend.domain.shadow_models import ShadowEvent
from backend.services.telegram_publication_policy import (
    evaluate_dvp_root,
    evaluate_orb_root,
)

NOW = datetime(2026, 9, 9, 20, 0, tzinfo=timezone.utc)


def _dvp(**changes):
    event = ShadowEvent(
        event_id="dvp-quality-1",
        symbol="EURUSD",
        timeframe="M15",
        direction="BULLISH",
        pattern_type="BULLISH_ENGULFING",
        pivot_1_time="2026-09-09T19:20:00+00:00",
        pivot_1_price=1.1000,
        pivot_2_time="2026-09-09T19:45:00+00:00",
        pivot_2_price=1.0980,
        relative_volume=1.42,
        activated_at="2026-09-09T16:00:00+00:00",
        processed_at="2026-09-09T19:59:30+00:00",
        entry_price=1.1010,
        initial_stop=1.0950,
        target_2R=1.1130,
    )
    for key, value in changes.items():
        setattr(event, key, value)
    return event


def test_dvp_root_requires_fresh_complete_prospective_evidence():
    assert evaluate_dvp_root(_dvp(), NOW).allowed is True
    stale = evaluate_dvp_root(
        _dvp(processed_at="2026-09-09T19:30:00+00:00"), NOW
    )
    assert stale.allowed is False
    assert stale.reason == "STALE_OR_INVALID_ROOT_TIME"


def test_dvp_root_rejects_bootstrap_and_incomplete_evidence():
    bootstrap = _dvp()
    bootstrap.metadata = {"bootstrap_detected": True}
    assert evaluate_dvp_root(bootstrap, NOW).reason == "NON_PROSPECTIVE_EVENT"
    incomplete = _dvp(pivot_2_price=0.0)
    decision = evaluate_dvp_root(incomplete, NOW)
    assert decision.allowed is False
    assert decision.reason == "DVP_EVIDENCE_INCOMPLETE"


def _orb(**changes):
    event = {
        "event_time": "2026-09-09T19:59:40+00:00",
        "symbol": "BTCUSDT",
        "signal_id": "orb-1",
        "signal_time": "2026-09-09T19:59:30+00:00",
        "t0": "2026-09-09T19:00:00+00:00",
        "range_high": "112.0", "range_low": "108.0",
        "entry": "112.5", "stop": "107.5", "target": "122.5",
    }
    event.update(changes)
    return event


def test_orb_root_requires_fresh_complete_opening_range_evidence():
    assert evaluate_orb_root(_orb(), NOW).allowed is True
    stale = evaluate_orb_root(
        _orb(event_time="2026-09-09T19:00:00+00:00"), NOW
    )
    assert stale.allowed is False
    assert stale.reason == "STALE_OR_INVALID_ROOT_TIME"


def test_orb_root_rejects_incomplete_or_invalid_range():
    missing = evaluate_orb_root(_orb(signal_time=""), NOW)
    assert missing.allowed is False
    assert missing.reason == "ORB_EVIDENCE_INCOMPLETE"
    invalid = evaluate_orb_root(_orb(range_high="107", range_low="108"), NOW)
    assert invalid.allowed is False
    assert invalid.reason == "ORB_RANGE_INVALID"
