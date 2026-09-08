from backend.domain.shadow_models import ShadowEvent, ShadowEventType
from backend.services.market_alert_template import (
    build_cycle_alert,
    build_dvp_alert,
    build_orb_alert,
    format_telegram_alert,
)


def test_dvp_template_uses_brazil_time_and_standard_name():
    event = ShadowEvent(
        event_id="dvp-preview",
        symbol="BTCUSDT",
        timeframe="M5",
        direction="BULLISH",
        entry_price=78450.2,
        initial_stop=78000.0,
        target_2R=79350.6,
        market_candle_time="2026-09-08T17:40:00+00:00",
    )
    alert = build_dvp_alert(ShadowEventType.ENTRY_ACTIVATED, event, {})
    assert alert["strategy_name"] == "HAGMARTK DVP"
    assert alert["event_time_brazil"] == "08/09/2026 • 14:40:00"
    assert alert["real_order_execution_enabled"] is False
    text = format_telegram_alert(alert)
    assert "HAGMARTK DVP" in text
    assert "Horário (Brasília)" in text
    assert "Nenhuma ordem real" in text


def test_cycle_template_uses_same_standard_and_multiple_targets():
    alert = build_cycle_alert({
        "event_type": "LIMIT_FILLED", "symbol": "XAUUSD", "timeframe": "M5",
        "direction": "BUY", "event_time": "2026-09-08T17:42:00+00:00",
        "levels": {"entry": 3620.15, "stop": 3612.4, "target_1": 3627.9,
                   "target_2": 3635.65, "target_3": 3643.4}, "payload": {},
    })
    assert alert["strategy_name"] == "HAGMARTK TEORIA DOS CICLOS"
    assert alert["event_time_brazil"] == "08/09/2026 • 14:42:00"
    text = format_telegram_alert(alert)
    assert "Alvo 1" in text and "Alvo 2" in text and "Alvo 3" in text
    assert "Nenhuma ordem real" in text


def test_orb_template_uses_same_standard_and_2r_target():
    alert = build_orb_alert("ENTRY_FILLED", {
        "symbol": "ETHUSDT", "event_time": "2026-09-08T17:45:00+00:00",
        "direction": "LONG", "entry": "4310.2", "stop": "4285.3", "target": "4360.0",
    })
    assert alert["strategy_name"] == "HAGMARTK ORB"
    assert alert["event_time_brazil"] == "08/09/2026 • 14:45:00"
    text = format_telegram_alert(alert)
    assert "Alvo 2R" in text
    assert "Nenhuma ordem real" in text
