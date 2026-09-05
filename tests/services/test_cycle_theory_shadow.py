from datetime import datetime
from zoneinfo import ZoneInfo

from backend.services.cycle_theory_shadow import select_cycle_timeframe
from backend.services.cycle_theory_shadow_store import CycleTheoryShadowStore
from backend.services.telegram_notifier import TelegramConfig, TelegramNotifier
from fastapi.testclient import TestClient
from backend.api.app import app


def test_user_timeframe_policy_sunday_opening_then_weekday_m5():
    tz = ZoneInfo("America/Sao_Paulo")
    sunday = datetime(2026, 9, 6, 19, 0, tzinfo=tz)
    monday = datetime(2026, 9, 7, 9, 0, tzinfo=tz)
    forex = {"broker_path": r"Forex\EURUSD"}
    crypto = {"broker_path": r"Cryptos\BTCUSD"}

    assert select_cycle_timeframe(forex, sunday, opening_trade_seen=False) == "M15"
    assert select_cycle_timeframe(forex, sunday, opening_trade_seen=True) == "M5"
    assert select_cycle_timeframe(forex, monday, opening_trade_seen=False) == "M5"
    assert select_cycle_timeframe(crypto, sunday, opening_trade_seen=False) == "M5"


def test_cycle_shadow_store_is_append_only_and_policy_persistent(tmp_path):
    store = CycleTheoryShadowStore(str(tmp_path / "cycle.db"))
    event = {
        "event_id": "ev1", "candidate_id": "cycle_theory_v111_baseline",
        "parameter_hash": "a" * 64, "symbol": "EURUSD", "market": "FOREX",
        "timeframe": "M5", "event_type": "ORDER_SUBMITTED", "direction": "BUY",
        "event_time": "2026-09-07T12:00:00+00:00", "payload": {"paper": True},
    }
    assert store.add_event(event) is True
    assert store.add_event(event) is False
    assert store.summary()["events"] == 1
    assert store.get_policy("EURUSD", "2026-09-07") is False
    store.set_opening_trade_seen("EURUSD", "2026-09-07", True)
    assert store.get_policy("EURUSD", "2026-09-07") is True


def test_cycle_telegram_template_is_portuguese_spaced_and_paper_only():
    notifier = TelegramNotifier(TelegramConfig(True, "BOT_API", bot_token="x", chat_id="1"))
    text = notifier._format_cycle_message({
        "event_id": "ev", "event_type": "ORDER_SUBMITTED", "symbol": "XAUUSD",
        "timeframe": "M15", "direction": "BUY", "event_time": "2026-09-06T22:00:00+00:00",
        "levels": {
            "channel_high": 3500.0, "channel_low": 3480.0, "expansion": 3520.0,
            "entry": 3510.0, "stop": 3479.0, "target_1": 3550.0,
            "target_2": 3590.0, "target_3": 3630.0,
        },
        "payload": {"detail": "Ordem virtual gerada."},
    })
    assert "HAGMARTK SHADOW ? TEORIA DOS CICLOS V111" in text
    assert "ORDEM PAPER GERADA" in text
    assert "Tempo gr?fico: <b>M15</b>" in text
    assert "Alvo 1" in text and "Alvo 2" in text and "Alvo 3" in text
    assert "Ordem real: <b>N?O</b>" in text
    assert "Probabilidade de alvo: <b>n?o calibrada</b>" in text


def test_cycle_status_endpoint_is_safe_when_not_started(monkeypatch):
    monkeypatch.setenv("HAGMARTK_AUTOSTART", "0")
    with TestClient(app) as client:
        payload = client.get("/api/shadow/cycle-theory/status").json()
    assert payload["enabled"] is False
    assert payload["real_order_execution_enabled"] is False
    assert "token" not in payload and "chat_id" not in payload
