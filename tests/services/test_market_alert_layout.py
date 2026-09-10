from io import BytesIO

from PIL import Image

from backend.services.market_alert_image import (
    _resolve_label_tops,
    render_market_alert_chart,
)


def test_level_layout_separates_nearby_prices_and_stays_in_bounds():
    tops = _resolve_label_tops(
        [200.0, 203.0, 205.0],
        top=100.0,
        bottom=300.0,
        height=28.0,
        gap=8.0,
    )
    ordered = sorted(tops)
    assert ordered[0] >= 100.0
    assert ordered[-1] + 28.0 <= 300.0
    assert ordered[1] - ordered[0] >= 36.0
    assert ordered[2] - ordered[1] >= 36.0


def test_orb_chart_renders_with_close_entry_stop_target_levels():
    candles = []
    price = 0.0900
    for index in range(30):
        candles.append({
            "time": f"2026-09-09T20:{index:02d}:00+00:00",
            "open": price,
            "high": price + 0.00015,
            "low": price - 0.00015,
            "close": price + 0.00003,
            "tick_volume": 100 + index,
        })
        price += 0.00001
    alert = {
        "strategy": "HAGMARTK ORB",
        "strategy_name": "HAGMARTK ORB",
        "strategy_key": "ORB",
        "symbol": "1INCHUSDT",
        "timeframe": "M5",
        "direction": "VENDA",
        "event_time_utc": "2026-09-09T20:25:00+00:00",
        "entry": 0.09022,
        "stop": 0.09058,
        "targets": [{"label": "Alvo 2R", "value": 0.08950}],
    }
    evidence = {
        "range_high": 0.09048,
        "range_low": 0.09018,
        "t0": "2026-09-09T20:00:00+00:00",
        "signal_time": "2026-09-09T20:25:00+00:00",
    }
    png = render_market_alert_chart(alert, candles, evidence)
    assert png is not None
    image = Image.open(BytesIO(png))
    assert image.size == (1280, 720)
    assert image.format == "PNG"
