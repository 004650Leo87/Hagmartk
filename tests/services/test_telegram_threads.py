import json

from backend.services.telegram_notifier import TelegramConfig, TelegramNotifier
from backend.services.telegram_thread_store import TelegramThreadStore
import backend.services.telegram_notifier as notifier_module


class FakeResponse:
    def __init__(self, message_id=1001):
        self.message_id = message_id
        self.status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True, "result": {"message_id": self.message_id}}


def _cycle_event(event_type, operation_id="op-cycle-1"):
    return {
        "event_id": f"evt-{event_type}",
        "event_type": event_type,
        "symbol": "BTCUSDT",
        "timeframe": "M5",
        "direction": "BUY",
        "event_time": "2026-09-09T10:00:00+00:00",
        "payload": {"operation_id": operation_id},
        "levels": {
            "channel_high": 110.0,
            "channel_low": 100.0,
            "expansion": 120.0,
            "c1_mid": 115.0,
            "entry": 112.0,
            "target_1": 122.0,
            "target_2": 132.0,
            "target_3": 142.0,
            "stop": 99.0,
        },
    }


def test_thread_store_keeps_first_root_and_closes(tmp_path):
    store = TelegramThreadStore(str(tmp_path / "threads.db"))
    store.set_root("TC:abc", "TC", "123", 10, "evt-root")
    store.set_root("TC:abc", "TC", "123", 99, "evt-duplicate")
    row = store.get("TC:abc")
    assert row["root_message_id"] == 10
    assert row["root_event_id"] == "evt-root"
    assert row["closed_at"] is None
    store.close("TC:abc")
    assert store.get("TC:abc")["closed_at"] is not None


def test_cycle_updates_reply_to_original_entry(monkeypatch, tmp_path):
    calls = []
    counter = iter([1001, 1002])
    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(next(counter))

    monkeypatch.setattr(notifier_module.requests, "post", fake_post)
    store = TelegramThreadStore(str(tmp_path / "threads.db"))
    notifier = TelegramNotifier(
        TelegramConfig(True, "BOT_API", bot_token="secret", chat_id="123"),
        thread_store=store,
    )
    monkeypatch.setattr(notifier, "_load_candles", lambda alert: [])

    notifier._safe_send_cycle(_cycle_event("LIMIT_FILLED"))
    notifier._safe_send_cycle(_cycle_event("TARGET_LEVEL_REACHED"))

    assert len(calls) == 2
    root_payload = calls[0][1]["json"]
    update_payload = calls[1][1]["json"]
    assert "reply_parameters" not in root_payload
    assert update_payload["reply_parameters"]["message_id"] == 1001
    row = store.get("TC:op-cycle-1")
    assert row["root_message_id"] == 1001


def test_root_entry_uses_chart_photo_when_available(monkeypatch, tmp_path):
    calls = []
    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(2001)

    monkeypatch.setattr(notifier_module.requests, "post", fake_post)
    monkeypatch.setattr(notifier_module, "render_market_alert_chart", lambda *a, **k: b"PNG")
    store = TelegramThreadStore(str(tmp_path / "threads-photo.db"))
    notifier = TelegramNotifier(
        TelegramConfig(True, "BOT_API", bot_token="secret", chat_id="123"),
        thread_store=store,
    )
    monkeypatch.setattr(notifier, "_load_candles", lambda alert: [{"time": "2026-09-09T10:00:00+00:00"}] * 8)

    notifier._safe_send_cycle(_cycle_event("LIMIT_FILLED", "op-photo"))

    assert len(calls) == 1
    assert calls[0][0].endswith("/sendPhoto")
    assert calls[0][1]["files"]["photo"][1] == b"PNG"
    assert "caption" in calls[0][1]["data"]
    assert store.get("TC:op-photo")["root_message_id"] == 2001


def test_final_cycle_event_closes_thread(monkeypatch, tmp_path):
    counter = iter([3001, 3002])
    monkeypatch.setattr(
        notifier_module.requests, "post",
        lambda url, **kwargs: FakeResponse(next(counter)),
    )
    store = TelegramThreadStore(str(tmp_path / "threads-close.db"))
    notifier = TelegramNotifier(
        TelegramConfig(True, "BOT_API", bot_token="secret", chat_id="123"),
        thread_store=store,
    )
    monkeypatch.setattr(notifier, "_load_candles", lambda alert: [])
    notifier._safe_send_cycle(_cycle_event("LIMIT_FILLED", "op-close"))
    notifier._safe_send_cycle(_cycle_event("STOP_LOSS", "op-close"))
    row = store.get("TC:op-close")
    assert row["root_message_id"] == 3001
    assert row["closed_at"] is not None


def test_bot_api_retries_after_429(monkeypatch, tmp_path):
    calls = []
    sleeps = []

    class RateLimited(FakeResponse):
        def __init__(self):
            super().__init__()
            self.status_code = 429
        def json(self):
            return {"ok": False, "parameters": {"retry_after": 2}}

    responses = iter([RateLimited(), FakeResponse(4001)])
    monkeypatch.setattr(notifier_module.requests, "post", lambda url, **kwargs: calls.append(url) or next(responses))
    monkeypatch.setattr(notifier_module.time, "sleep", lambda seconds: sleeps.append(seconds))
    notifier = TelegramNotifier(TelegramConfig(True, "BOT_API", bot_token="secret", chat_id="123"), thread_store=TelegramThreadStore(str(tmp_path / "retry.db")))
    response = notifier._telegram_post("https://api.telegram.test/sendMessage", json={"text": "x"})
    assert response.status_code == 200
    assert len(calls) == 2
    assert 2.0 in sleeps
