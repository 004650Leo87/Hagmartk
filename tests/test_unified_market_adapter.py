from datetime import datetime, timezone

from backend.engines.market.unified_market_adapter import (
    BINANCE_PROVIDER,
    MT5_PROVIDER,
    UnifiedMarketAdapter,
)


class FakeMT5:
    def __init__(self):
        self.connected = False

    def connect(self): self.connected = True
    def disconnect(self): self.connected = False
    def get_symbols(self):
        return [{"symbol": "EURUSD", "category": "FOREX", "point": 0.00001, "digits": 5}]
    def get_quote(self, symbol):
        return {"symbol": symbol, "bid": 1.1, "ask": 1.1001, "time": "2026-09-05T02:00:00+00:00"}
    def get_candles(self, symbol, timeframe, count=None, from_time=None, to_time=None):
        return [{"time": "2026-09-05T01:55:00+00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
    def get_ticks(self, symbol, from_time, to_time): return [{"time": from_time.isoformat(), "bid": 1.1, "ask": 1.2}]
    def get_supported_timeframes(self): return {5: "M5"}
    def get_runtime_scope(self): return {"broker_time_offset_hours": 3, "server": "Tickmill-Live"}
    def get_connection_info(self): return {"connected": self.connected}


class FakeBinance:
    def __init__(self): self.connected = False
    def connect(self): self.connected = True
    def disconnect(self): self.connected = False
    def get_symbols(self):
        return [{"symbol": "BTCUSDT", "category": "CRYPTO", "provider": BINANCE_PROVIDER,
                 "market_type": "PERPETUAL_FUTURES", "point": 0.1, "digits": 1}]
    def get_quote(self, symbol):
        return {"symbol": symbol, "provider": BINANCE_PROVIDER, "bid": 80000, "ask": 80000.1,
                "time": "2026-09-05T02:00:00+00:00"}
    def get_candles(self, symbol, timeframe, count=None, from_time=None, to_time=None):
        return [{"time": "2026-09-05T01:55:00+00:00", "open": 80000, "high": 80100,
                 "low": 79900, "close": 80050}]
    def get_book_tickers(self):
        return {"BTCUSDT": self.get_quote("BTCUSDT")}
    def get_supported_timeframes(self): return {5: "M5", 16386: "H2"}
    def get_connection_info(self):
        return {"connected": self.connected, "read_only": True,
                "real_order_execution_enabled": False}


def make_adapter():
    adapter = UnifiedMarketAdapter()
    adapter.mt5 = FakeMT5()
    adapter.binance = FakeBinance()
    return adapter


def test_unified_catalog_and_routing_are_provider_aware_and_read_only():
    adapter = make_adapter()
    adapter.connect()
    rows = adapter.get_symbols()
    assert {row["symbol"] for row in rows} == {"EURUSD", "BTCUSDT"}
    assert adapter.provider_for_symbol("EURUSD") == MT5_PROVIDER
    assert adapter.provider_for_symbol("BTCUSDT") == BINANCE_PROVIDER
    assert adapter.get_quote("BTCUSDT")["provider"] == BINANCE_PROVIDER
    assert adapter.get_quote("EURUSD")["provider"] == MT5_PROVIDER
    info = adapter.get_connection_info()
    assert info["read_only"] is True
    assert info["real_order_execution_enabled"] is False


def test_unified_bulk_quotes_and_binance_tick_gap_do_not_fabricate_data():
    adapter = make_adapter()
    adapter.connect()
    quotes = adapter.get_quotes_bulk()
    assert set(quotes) == {"EURUSD", "BTCUSDT"}
    start = datetime(2026, 9, 5, 1, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 5, 1, 1, tzinfo=timezone.utc)
    assert adapter.get_ticks("BTCUSDT", start, end) == []
    assert len(adapter.get_ticks("EURUSD", start, end)) == 1
    scope = adapter.get_runtime_scope()
    assert scope["market_data_mode"] == "UNIFIED_READ_ONLY"
