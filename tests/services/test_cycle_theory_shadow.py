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
    assert "HAGMARTK TDC" in text
    assert "OPORTUNIDADE EM OBSERVAÇÃO" in text
    assert "<b>Gráfico:</b> M15" in text
    assert "Alvo 1" in text and "Alvo 2" in text and "Alvo 3" in text
    assert "Nenhuma ordem real foi enviada." in text


def test_cycle_status_endpoint_is_safe_when_not_started(monkeypatch):
    monkeypatch.setenv("HAGMARTK_AUTOSTART", "0")
    with TestClient(app) as client:
        payload = client.get("/api/shadow/cycle-theory/status").json()
    assert payload["enabled"] is False
    assert payload["real_order_execution_enabled"] is False
    assert "token" not in payload and "chat_id" not in payload


def test_binance_futures_is_always_treated_as_24_7_m5():
    tz = ZoneInfo("America/Sao_Paulo")
    sunday = datetime(2026, 9, 6, 19, 0, tzinfo=tz)
    binance = {
        "symbol": "BTCUSDT",
        "category": "CRYPTO",
        "provider": "BINANCE_USDM_FUTURES",
        "broker_path": "Binance USD-M/USDT/PERPETUAL",
    }
    assert select_cycle_timeframe(binance, sunday, opening_trade_seen=False) == "M5"


def test_binance_context_uses_exchange_utc_clock_not_mt5_server_clock(tmp_path):
    from backend.services.cycle_theory_shadow import CycleTheoryProspectiveScanner
    from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock

    scanner = CycleTheoryProspectiveScanner(store=CycleTheoryShadowStore(str(tmp_path / "cycle_clock.db")))
    scanner.clock = CycleTheoryBrokerClock(offset_hours=3.0)
    row = {
        "symbol": "BTCUSDT", "category": "CRYPTO", "provider": "BINANCE_USDM_FUTURES",
        "point": 0.1, "digits": 1, "volume_step": 0.001,
        "volume_min": 0.001, "volume_max": 1000.0,
    }
    context = scanner._new_context(row, "M5")
    assert context.clock is not None
    assert context.clock.offset_hours == 0.0


def test_cycle_live_universe_defaults_to_curated_fidelity_symbols(monkeypatch, tmp_path):
    from backend.services.cycle_theory_shadow import CycleTheoryProspectiveScanner
    monkeypatch.delenv("HAGMARTK_CYCLE_LIVE_SYMBOLS", raising=False)
    class Adapter:
        def get_symbols(self):
            return [
                {"symbol": "EURUSD", "category": "FOREX"},
                {"symbol": "XAUUSD", "category": "METALS"},
                {"symbol": "BTCUSDT", "category": "CRYPTO", "provider": "BINANCE_USDM_FUTURES"},
                {"symbol": "NIGHTUSDT", "category": "CRYPTO", "provider": "BINANCE_USDM_FUTURES"},
            ]
    scanner = CycleTheoryProspectiveScanner(store=CycleTheoryShadowStore(str(tmp_path / "curated.db")))
    assert scanner.refresh_universe(Adapter()) == 2
    assert set(scanner.symbol_rows) == {"EURUSD", "XAUUSD"}
    assert scanner.provider_catalog_size == 4


def test_cycle_live_universe_can_be_explicitly_overridden(monkeypatch, tmp_path):
    from backend.services.cycle_theory_shadow import CycleTheoryProspectiveScanner
    monkeypatch.setenv("HAGMARTK_CYCLE_LIVE_SYMBOLS", "EURUSD,BTCUSDT")
    class Adapter:
        def get_symbols(self):
            return [
                {"symbol": "EURUSD", "category": "FOREX"},
                {"symbol": "BTCUSDT", "category": "CRYPTO", "provider": "BINANCE_USDM_FUTURES"},
                {"symbol": "NIGHTUSDT", "category": "CRYPTO", "provider": "BINANCE_USDM_FUTURES"},
            ]
    scanner = CycleTheoryProspectiveScanner(store=CycleTheoryShadowStore(str(tmp_path / "override.db")))
    assert scanner.refresh_universe(Adapter()) == 2
    assert set(scanner.symbol_rows) == {"EURUSD", "BTCUSDT"}


def test_cycle_recovery_event_is_persisted_but_not_notified(monkeypatch, tmp_path):
    from datetime import timezone
    from backend.services.cycle_theory_shadow import CycleTheoryProspectiveScanner
    from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
    class FakeNotifier:
        def __init__(self): self.calls = []
        def notify_cycle_async(self, event): self.calls.append(event); return True
    notifier = FakeNotifier()
    scanner = CycleTheoryProspectiveScanner(store=CycleTheoryShadowStore(str(tmp_path / "replay.db")), notifier=notifier)
    scanner.clock = CycleTheoryBrokerClock(offset_hours=0.0)
    row = {"symbol":"EURUSD","category":"FOREX","point":0.00001,"digits":5,"volume_step":0.01,"volume_min":0.01,"volume_max":100.0}
    context = scanner._new_context(row, "M5")
    inserted = scanner._record_event(context, "LIMIT_FILLED", {"ticket":1}, datetime(2026,9,9,20,0,tzinfo=timezone.utc), publish_notification=False)
    assert inserted is True
    assert notifier.calls == []


def test_cycle_telegram_is_fail_closed_during_fidelity_review(monkeypatch, tmp_path):
    from backend.services.cycle_theory_shadow import CycleTheoryProspectiveScanner
    monkeypatch.delenv("HAGMARTK_CYCLE_TELEGRAM_ENABLED", raising=False)
    class FakeNotifier:
        def __init__(self): self.calls = []
        def notify_cycle_async(self, event): self.calls.append(event); return True
        def status(self): return {"ready": True}
    notifier = FakeNotifier()
    scanner = CycleTheoryProspectiveScanner(store=CycleTheoryShadowStore(str(tmp_path / "quarantine.db")), notifier=notifier)
    assert scanner.status()["telegram_publish_enabled"] is False
    assert scanner.status()["telegram_publish_policy"] == "FAIL_CLOSED_DURING_FIDELITY_REVIEW"
