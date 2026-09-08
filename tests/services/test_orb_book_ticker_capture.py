from datetime import datetime, timedelta, timezone

from backend.services.orb_binance_capture import BinanceOrbBookTickerCapture


def _msg(symbol, when, bid, ask):
    return {
        "e": "bookTicker", "s": symbol,
        "E": int(when.timestamp() * 1000),
        "b": str(bid), "a": str(ask),
    }


def test_capture_preserves_first_quote_after_m5_boundary():
    cap = BinanceOrbBookTickerCapture()
    cap.update_symbols(["BTCUSDT"])
    t0 = datetime(2026, 9, 9, 0, 20, tzinfo=timezone.utc)
    assert cap.ingest_message(_msg("BTCUSDT", t0 + timedelta(milliseconds=100), 100, 101))
    assert cap.ingest_message(_msg("BTCUSDT", t0 + timedelta(milliseconds=200), 102, 103))
    first = cap.first_quote("BTCUSDT", t0)
    assert first is not None
    assert first["bid"] == 100
    assert first["ask"] == 101


def test_capture_stop_target_time_priority_is_event_ordered():
    cap = BinanceOrbBookTickerCapture()
    cap.update_symbols(["BTCUSDT"])
    t0 = datetime(2026, 9, 9, 0, 20, tzinfo=timezone.utc)
    cap.connection_epoch = 1
    cap.register_watch("BTCUSDT", "LONG", 99, 120, t0 + timedelta(minutes=100), t0)
    cap.ingest_message(_msg("BTCUSDT", t0 + timedelta(seconds=1), 98, 121))
    trigger = cap.pop_trigger("BTCUSDT")
    assert trigger["reason"] == "STOP"

def test_capture_marks_reconnect_gap_for_open_watch():
    cap = BinanceOrbBookTickerCapture()
    cap.update_symbols(["BTCUSDT"])
    t0 = datetime(2026, 9, 9, 0, 20, tzinfo=timezone.utc)
    cap.connection_epoch = 2
    cap.register_watch("BTCUSDT", "SHORT", 120, 80, t0 + timedelta(minutes=100), t0)
    cap.connection_epoch = 3
    cap.ingest_message(_msg("BTCUSDT", t0 + timedelta(seconds=2), 100, 101))
    trigger = cap.pop_trigger("BTCUSDT")
    assert trigger["reason"] == "DATA_GAP"
