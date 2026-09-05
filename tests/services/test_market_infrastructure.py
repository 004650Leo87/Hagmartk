import sys
import types
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.constants import SUPPORTED_TIMEFRAMES, categorize_symbol
from backend.services.market_service import MarketService


def make_fake_mt5_service_module():
    fake = types.SimpleNamespace()

    def last_error():
        return (0, "ok")

    def initialize():
        return True

    def shutdown():
        return True

    def symbols_get():
        return [
            types.SimpleNamespace(name="EURUSD"),
            types.SimpleNamespace(name="XAUUSD"),
            types.SimpleNamespace(name="BTCUSD"),
            types.SimpleNamespace(name="UNKNOWN123"),
        ]

    def symbol_info(name):
        if name == "INVALID_SYMBOL":
            return None

        path_map = {
            "EURUSD": "Forex/Majors",
            "XAUUSD": "CFD/Metals",
            "BTCUSD": "Crypto/Pairs",
            "UNKNOWN123": "Custom/Group",
        }
        desc_map = {
            "EURUSD": "Euro vs US Dollar",
            "XAUUSD": "Gold Spot",
            "BTCUSD": "Bitcoin vs USD",
            "UNKNOWN123": "Unknown Asset",
        }
        visible = name != "BTCUSD"

        return types.SimpleNamespace(
            name=name,
            description=desc_map.get(name, "Generic"),
            path=path_map.get(name, ""),
            visible=visible,
            selected=True,
            digits=5 if name == "EURUSD" else 2,
            point=0.00001 if name == "EURUSD" else 0.01,
            currency_base="USD",
            currency_profit="USD",
            trade_mode=0,
            spread=12,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            margin_initial=1000.0,
            trade_contract_size=100000.0,
        )

    def symbol_select(name, enable):
        return True

    def copy_rates_from_pos(symbol, timeframe, pos, count):
        if symbol == "UNKNOWN123":
            return None

        out = []
        base_time = 1620000000 + (pos * 60)
        for i in range(count):
            out.append(
                {
                    "time": base_time + (i * 60),
                    "open": 1.0 + (i * 0.01),
                    "high": 1.05 + (i * 0.01),
                    "low": 0.95 + (i * 0.01),
                    "close": 1.02 + (i * 0.01),
                    "tick_volume": 100 + i,
                    "spread": 2,
                    "real_volume": 10 + i,
                }
            )
        return out

    fake.last_error = last_error
    fake.initialize = initialize
    fake.shutdown = shutdown
    fake.symbols_get = symbols_get
    fake.symbol_info = symbol_info
    fake.symbol_select = symbol_select
    fake.copy_rates_from_pos = copy_rates_from_pos

    return fake


def test_categorize_symbol_fallbacks():
    assert categorize_symbol("Forex/Major", "EURUSD", "Euro vs Dollar") == "FOREX"
    assert categorize_symbol("CFD/Metals", "XAUUSD", "Gold Spot") == "METALS"
    assert categorize_symbol("CFD/Energy", "WTI", "Crude Oil") == "ENERGY"
    assert categorize_symbol("Crypto", "BTCUSD", "Bitcoin") == "CRYPTO"
    assert categorize_symbol("Indices", "US30", "Wall Street 30") == "INDICES"
    assert categorize_symbol("Stocks", "AAPL", "Apple Inc") == "STOCKS"
    assert categorize_symbol("CustomGroup", "XYZ", "Random Item") == "OTHER"


def test_supported_timeframes_centralization():
    assert "M1" in SUPPORTED_TIMEFRAMES
    assert "M5" in SUPPORTED_TIMEFRAMES
    assert "H1" in SUPPORTED_TIMEFRAMES
    assert "D1" in SUPPORTED_TIMEFRAMES
    assert SUPPORTED_TIMEFRAMES["M5"] == 5
    assert SUPPORTED_TIMEFRAMES["H1"] == 16385


def test_detailed_symbols_and_candles_infrastructure(monkeypatch):
    fake_mt5 = make_fake_mt5_service_module()
    monkeypatch.setattr("backend.services.market_service.mt5", fake_mt5)

    service = MarketService()
    # Isolate this legacy MT5 infrastructure test from external providers.
    monkeypatch.setattr(service.mt5, "connect", lambda: True)
    monkeypatch.setattr(service, "_ensure_binance_connection", lambda: None)
    monkeypatch.setattr(service.binance_futures, "get_symbols", lambda: [])

    # 1. Test detailed_symbols
    detailed = service.detailed_symbols()
    assert isinstance(detailed, list)
    assert len(detailed) == 4

    eurusd = next(s for s in detailed if s["symbol"] == "EURUSD")
    assert eurusd["category"] == "FOREX"
    assert eurusd["broker_path"] == "Forex/Majors"
    assert eurusd["digits"] == 5
    assert eurusd["volume_min"] == 0.01

    btc = next(s for s in detailed if s["symbol"] == "BTCUSD")
    assert btc["category"] == "CRYPTO"

    # 2. Test candles_detailed with valid symbol and offset
    res = service.candles_detailed("EURUSD", timeframe=5, bars=10, offset=0)
    assert res["symbol"] == "EURUSD"
    assert res["timeframe"] == 5
    assert res["requested_bars"] == 10
    assert res["returned_bars"] == 10
    assert res["offset"] == 0
    assert res["has_more"] is True
    assert res["earliest_timestamp"] is not None
    assert res["latest_timestamp"] is not None
    assert len(res["candles"]) == 10

    # 3. Test candles_detailed with symbol that returns no history
    res_empty = service.candles_detailed("UNKNOWN123", timeframe=5, bars=10, offset=0)
    assert res_empty["symbol"] == "UNKNOWN123"
    assert res_empty["returned_bars"] == 0
    assert res_empty["has_more"] is False
    assert res_empty["earliest_timestamp"] is None
    assert res_empty["candles"] == []

    # 4. Test invalid symbol raises ValueError
    with pytest.raises(ValueError, match="não foi encontrado"):
        service.candles_detailed("INVALID_SYMBOL", timeframe=5, bars=10)


def test_detailed_symbols_and_candles_routes(monkeypatch):
    fake_mt5 = make_fake_mt5_service_module()
    monkeypatch.setattr("backend.services.market_service.mt5", fake_mt5)
    monkeypatch.setattr("backend.services.market_service.MarketService._ensure_connection", lambda self: None)

    client = TestClient(app)

    # GET /market/symbols/detailed
    res = client.get("/market/symbols/detailed")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "broker_path" in data[0]
    assert "category" in data[0]

    # GET /market/candles/EURUSD/detailed
    res_candles = client.get("/market/candles/EURUSD/detailed?timeframe=5&bars=5&offset=0")
    assert res_candles.status_code == 200
    candle_data = res_candles.json()
    assert candle_data["symbol"] == "EURUSD"
    assert candle_data["returned_bars"] == 5
    assert candle_data["has_more"] is True

    # GET /market/candles/INVALID_SYMBOL/detailed returns 404
    res_invalid = client.get("/market/candles/INVALID_SYMBOL/detailed?timeframe=5&bars=5")
    assert res_invalid.status_code == 404
