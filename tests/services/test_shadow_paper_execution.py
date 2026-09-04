from __future__ import annotations

from backend.domain.shadow_models import ShadowEvent, ShadowState
from backend.services.paper_execution import ShadowPaperExecutionEngine
from backend.services.shadow_store import ShadowStoreRepository


def _store(tmp_path):
    return ShadowStoreRepository(str(tmp_path / "paper.db"))


def _armed_event(direction: str = "BULLISH", event_id: str = "evt_paper_1") -> ShadowEvent:
    bullish = direction == "BULLISH"
    return ShadowEvent(
        event_id=event_id,
        symbol="EURUSD",
        timeframe="M15",
        direction=direction,
        pattern_type="BULLISH_ENGULFING" if bullish else "BEARISH_ENGULFING",
        confluence_time="2026-09-04T10:00:00+00:00",
        armed_at="2026-09-04T10:00:00+00:00",
        activation_level=1.1000,
        initial_stop=1.0900 if bullish else 1.1100,
        current_state=ShadowState.ARMED.value,
        market_candle_time="2026-09-04T10:00:00+00:00",
        created_at="2026-09-04T10:00:01+00:00",
        updated_at="2026-09-04T10:00:01+00:00",
        metadata={"execution_mode": "SHADOW_PAPER", "broker_order_sent": False},
    )

def _candle(t: str, o: float, h: float, l: float, c: float) -> dict:
    return {"time": t, "open": o, "high": h, "low": l, "close": c}


def test_bullish_paper_activation_uses_gap_aware_entry(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    assert store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)

    engine.process_closed_candle(
        "EURUSD", "M15",
        _candle("2026-09-04T10:15:00+00:00", 1.1020, 1.1060, 1.0950, 1.1040),
    )
    saved = store.get_event(evt.event_id)
    assert saved.current_state == ShadowState.ACTIVATED.value
    assert saved.entry_price == 1.1020
    assert round(saved.initial_risk, 6) == 0.0120
    assert round(saved.target_2R, 6) == 1.1260
    assert saved.activated_at == "2026-09-04T10:15:00+00:00"
    assert saved.metadata["broker_order_sent"] is False
    assert any(t.reason == "PAPER_ENTRY_TRIGGERED" for t in store.get_transitions(evt.event_id))

def test_paper_target_emits_1r_and_target_transitions(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T10:15:00+00:00", 1.1000, 1.1010, 1.0950, 1.1005))
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T10:30:00+00:00", 1.1005, 1.1210, 1.0990, 1.1200))

    saved = store.get_event(evt.event_id)
    assert saved.current_state == ShadowState.TARGET_2R.value
    assert saved.milestone_1r_reached is True
    assert saved.metadata["realized_r_gross"] == 2.0
    reasons = [t.reason for t in store.get_transitions(evt.event_id)]
    assert "PAPER_MILESTONE_1R" in reasons
    assert "TARGET_2R_REACHED" in reasons


def test_same_bar_target_and_stop_is_stop_first(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T10:15:00+00:00", 1.1000, 1.1010, 1.0950, 1.1005))
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T10:30:00+00:00", 1.1005, 1.1210, 1.0890, 1.1000))

    saved = store.get_event(evt.event_id)
    assert saved.current_state == ShadowState.STOPPED.value
    assert saved.metadata["same_bar_ambiguous"] is True
    assert saved.metadata["terminal_reason"] == "TARGET_AND_STOP_SAME_BAR_STOP_FIRST"
    assert saved.metadata["realized_r_gross"] == -1.0

def test_armed_setup_expires_only_after_five_future_bars(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)
    for minute in (15, 30, 45):
        engine.process_closed_candle("EURUSD", "M15", _candle(f"2026-09-04T10:{minute:02d}:00+00:00", 1.0950, 1.0990, 1.0920, 1.0960))
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T11:00:00+00:00", 1.0950, 1.0990, 1.0920, 1.0960))
    assert store.get_event(evt.event_id).current_state == ShadowState.ARMED.value
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T11:15:00+00:00", 1.0950, 1.0990, 1.0920, 1.0960))
    saved = store.get_event(evt.event_id)
    assert saved.current_state == ShadowState.EXPIRED.value
    assert saved.metadata["paper_activation_bars_elapsed"] == 5


def test_invalidation_wins_before_activation(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)
    engine.process_closed_candle("EURUSD", "M15", _candle("2026-09-04T10:15:00+00:00", 1.1000, 1.1050, 1.0890, 1.1000))
    saved = store.get_event(evt.event_id)
    assert saved.current_state == ShadowState.INVALIDATED.value
    assert saved.activated_at == ""
    assert saved.metadata["terminal_reason"] == "INVALIDATED_BEFORE_ACTIVATION"

def test_existing_armed_event_replays_downtime_candles(tmp_path):
    store = _store(tmp_path)
    evt = _armed_event()
    store.save_event(evt)
    engine = ShadowPaperExecutionEngine(store)
    candles = [
        _candle("2026-09-04T10:15:00+00:00", 1.0950, 1.0990, 1.0920, 1.0960),
        _candle("2026-09-04T10:30:00+00:00", 1.1010, 1.1050, 1.0950, 1.1030),
        _candle("2026-09-04T10:45:00+00:00", 1.1030, 1.1230, 1.1000, 1.1210),
    ]
    engine.process_candles("EURUSD", "M15", candles)
    saved = store.get_event(evt.event_id)
    assert saved.activated_at == "2026-09-04T10:30:00+00:00"
    assert saved.entry_price == 1.1010
    assert saved.current_state == ShadowState.TARGET_2R.value
    assert saved.bars_since_activation == 1


def test_shadow_statistics_exclude_test_fixture(tmp_path):
    store = _store(tmp_path)
    fixture = _armed_event(event_id="test_fixture_1")
    fixture.current_state = ShadowState.TARGET_2R.value
    fixture.activated_at = "2026-09-04T10:15:00+00:00"
    fixture.target_2R = 1.12
    store.save_event(fixture)
    stats = store.get_shadow_statistics("2026-09-04T09:00:00+00:00")
    assert stats.total_events_detected == 0
    assert stats.targets_reached_count == 0
    assert stats.net_r_shadow == 0.0