from backend.engines.market.binance_usdm_futures_adapter import (
    BinanceUSDMFuturesMarketAdapter,
    PROVIDER_ID,
)
from backend.services.market_service import MarketService


class FakeBinance(BinanceUSDMFuturesMarketAdapter):
    def __init__(self):
        super().__init__()
        self.calls = []

    def _request_json(self, path, params=None):
        self.calls.append((path, params or {}))
        if path == "/fapi/v1/ping":
            return {}
        if path == "/fapi/v1/exchangeInfo":
            return {
                "symbols": [
                    {
                        "symbol": "BTCUSDT", "pair": "BTCUSDT", "status": "TRADING",
                        "contractType": "PERPETUAL", "baseAsset": "BTC", "quoteAsset": "USDT",
                        "marginAsset": "USDT", "pricePrecision": 2,
                        "filters": [
                            {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                            {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
                        ],
                    },
                    {
                        "symbol": "ETHUSDT_260925", "pair": "ETHUSDT", "status": "TRADING",
                        "contractType": "CURRENT_QUARTER", "baseAsset": "ETH", "quoteAsset": "USDT",
                        "marginAsset": "USDT", "pricePrecision": 2, "filters": [],
                    },
                    {
                        "symbol": "OLDUSDT", "pair": "OLDUSDT", "status": "SETTLING",
                        "contractType": "PERPETUAL", "baseAsset": "OLD", "quoteAsset": "USDT",
                        "marginAsset": "USDT", "pricePrecision": 4, "filters": [],
                    },
                ]
            }
        if path == "/fapi/v1/ticker/bookTicker":
            return {"symbol": "BTCUSDT", "bidPrice": "80000.10", "askPrice": "80000.20", "time": 1788573600000}
        if path == "/fapi/v1/ticker/price":
            return {"symbol": "BTCUSDT", "price": "80000.15", "time": 1788573600000}
        if path == "/fapi/v1/klines":
            return [
                [1788573300000, "79900", "80100", "79800", "80000", "12.5", 1788573599999, "999000", 321, "7.5", "600000", "0"],
                [1788573600000, "80000", "80200", "79950", "80100", "14.0", 1788573899999, "1120000", 400, "8.0", "640000", "0"],
            ]
        if path == "/fapi/v1/premiumIndex":
            return {"symbol": "BTCUSDT", "markPrice": "80001", "indexPrice": "80002", "lastFundingRate": "0.0001", "nextFundingTime": 1788595200000}
        raise AssertionError(path)


def test_adapter_filters_to_trading_perpetual_and_is_read_only():
    adapter = FakeBinance()
    adapter.connect()
    symbols = adapter.get_symbols()
    assert [item["symbol"] for item in symbols] == ["BTCUSDT"]
    meta = symbols[0]
    assert meta["provider"] == PROVIDER_ID
    assert meta["market_type"] == "PERPETUAL_FUTURES"
    assert meta["read_only"] is True
    assert meta["real_order_execution_enabled"] is False
    assert meta["point"] == 0.1
    assert adapter.get_connection_info()["authentication"] == "NONE"


def test_quote_candles_and_futures_metrics_are_normalized():
    adapter = FakeBinance()
    adapter.connect()
    quote = adapter.get_quote("BTCUSDT")
    assert quote["provider"] == PROVIDER_ID
    assert quote["bid"] == 80000.10
    assert quote["ask"] == 80000.20
    assert quote["spread_points"] == 1.0

    candles = adapter.get_candles("BTCUSDT", "M5", count=2)
    assert len(candles) == 2
    assert candles[0]["tick_volume"] == 321
    assert candles[0]["real_volume"] == 12.5
    assert candles[0]["provider"] == PROVIDER_ID
    assert adapter.get_mark_price("BTCUSDT")["last_funding_rate"] == 0.0001


def test_market_service_routes_binance_without_mt5_dependency(monkeypatch):
    service = MarketService()
    fake = FakeBinance()
    fake.connect()
    service.binance_futures = fake
    service._binance_connected = True

    def fail_mt5():
        raise AssertionError("MT5 should not be required for a Binance futures symbol")

    monkeypatch.setattr(service, "_ensure_connection", fail_mt5)

    quote = service.quote("BTCUSDT")
    assert quote["provider"] == PROVIDER_ID

    candles = service.candles("BTCUSDT", 5, bars=2)
    assert len(candles) == 2
    assert str(candles.iloc[0]["provider"]) == PROVIDER_ID

    detailed = service.candles_detailed("BTCUSDT", 5, bars=2)
    assert detailed["provider"] == PROVIDER_ID
    assert detailed["returned_bars"] == 2
