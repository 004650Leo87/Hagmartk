import pytest
from fastapi import HTTPException

from backend.api import shadow_routes
from backend.domain.shadow_models import ShadowEvent, ShadowEventType, ShadowState
from backend.services.alert_engine import InternalShadowPublisher
from backend.services.shadow_store import ShadowStoreRepository
from backend.services.telegram_notifier import TelegramConfig, TelegramNotifier


def _event(state=ShadowState.ARMED.value):
    return ShadowEvent(
        event_id="evt_telegram_001",
        symbol="EURUSD",
        timeframe="M15",
        direction="BULLISH",
        pattern_type="BULLISH_ENGULFING",
        relative_volume=1.42,
        activation_level=1.101,
        initial_stop=1.095,
        target_2R=1.113,
        current_state=state,
        confluence_time="2026-09-04T16:45:00+00:00",
    )

def test_status_never_exposes_secrets():
    cfg = TelegramConfig(enabled=True, mode="BOT_API", bot_token="secret-token", chat_id="123456")
    status = TelegramNotifier(cfg).status()
    assert status == {
        "enabled": True,
        "configured": True,
        "mode": "BOT_API",
        "ready": True,
        "secrets_exposed": False,
    }
    assert "secret-token" not in str(status)
    assert "123456" not in str(status)


def test_message_model_armed_and_target():
    notifier = TelegramNotifier(TelegramConfig(enabled=False, mode="CONFIG_MISSING"))
    armed = notifier._format_event_message(ShadowEventType.SETUP_ARMED, _event(), {})
    assert "CONFIGURAÇÃO ARMADA" in armed
    assert "EURUSD" in armed and "M15" in armed and "COMPRA" in armed
    assert "HAGMARTK SHADOW • DVP" in armed
    assert "Ordem real: <b>NÃO</b>" in armed

    evt = _event(ShadowState.TARGET_2R.value)
    evt.entry_price = 1.101
    target = notifier._format_event_message(ShadowEventType.TARGET_REACHED, evt, {})
    assert "ALVO 2R ATINGIDO" in target
    assert "Resultado bruto: <b>+2.00R</b>" in target

def test_internal_publisher_forwards_allowed_event_to_notifier(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "telegram.db"))

    class FakeNotifier:
        def __init__(self):
            self.calls = []
        def notify_async(self, event_type, event, details):
            self.calls.append((event_type, event.event_id, dict(details)))
            return True

    fake = FakeNotifier()
    publisher = InternalShadowPublisher(store, telegram_notifier=fake)
    evt = _event()
    publisher.publish(
        ShadowEventType.SETUP_ARMED,
        evt,
        {"from_state": "DETECTED", "candle_timestamp": evt.confluence_time, "market_price": evt.activation_level},
    )
    assert len(store.get_transitions(evt.event_id)) == 1
    assert fake.calls[0][0] == ShadowEventType.SETUP_ARMED
    assert fake.calls[0][1] == evt.event_id


def test_disabled_notifier_does_not_spawn_delivery():
    notifier = TelegramNotifier(TelegramConfig(enabled=False, mode="WEBHOOK", webhook_url="https://example.invalid"))
    assert notifier.notify_async(ShadowEventType.SETUP_ARMED, _event(), {}) is False

def test_telegram_status_and_test_routes(monkeypatch):
    class FakeNotifier:
        def status(self):
            return {"enabled": True, "configured": True, "mode": "WEBHOOK", "ready": True, "secrets_exposed": False}
        def send_test_async(self):
            return True

    fake = FakeNotifier()
    monkeypatch.setattr(shadow_routes._scanner.publisher, "telegram_notifier", fake)
    status = shadow_routes.get_telegram_notification_status()
    assert status["ready"] is True
    result = shadow_routes.send_telegram_test_notification()
    assert result["accepted"] is True
    assert "url" not in result and "token" not in result and "chat_id" not in result

    status_route = next(r for r in shadow_routes.router.routes if r.path == "/api/shadow/notifications/telegram/status")
    test_route = next(r for r in shadow_routes.router.routes if r.path == "/api/shadow/notifications/telegram/test")
    assert status_route.methods == {"GET"}
    assert test_route.methods == {"POST"}


def test_telegram_test_route_rejects_unconfigured(monkeypatch):
    class FakeNotifier:
        def status(self):
            return {"enabled": False, "configured": False, "mode": "CONFIG_MISSING", "ready": False, "secrets_exposed": False}
    monkeypatch.setattr(shadow_routes._scanner.publisher, "telegram_notifier", FakeNotifier())
    with pytest.raises(HTTPException) as exc:
        shadow_routes.send_telegram_test_notification()
    assert exc.value.status_code == 409

def test_duplicate_transition_does_not_duplicate_telegram(tmp_path):
    store = ShadowStoreRepository(str(tmp_path / "telegram_dedup.db"))

    class FakeNotifier:
        def __init__(self):
            self.calls = 0
        def notify_async(self, event_type, event, details):
            self.calls += 1
            return True

    fake = FakeNotifier()
    publisher = InternalShadowPublisher(store, telegram_notifier=fake)
    evt = _event()
    details = {"from_state": "DETECTED", "candle_timestamp": evt.confluence_time, "reason": "PAPER_SETUP_ARMED"}
    publisher.publish(ShadowEventType.SETUP_ARMED, evt, details)
    publisher.publish(ShadowEventType.SETUP_ARMED, evt, details)
    assert len(store.get_transitions(evt.event_id)) == 1
    assert fake.calls == 1
