from backend.engines.market.binance_usdm_futures_adapter import BinanceUSDMFuturesMarketAdapter


def test_binance_24h_quote_volume_snapshot_is_normalized_and_cached(monkeypatch):
    adapter = BinanceUSDMFuturesMarketAdapter()
    calls = []

    def fake_request(path, params=None):
        calls.append((path, params))
        return [
            {"symbol": "BTCUSDT", "quoteVolume": "1000000.5"},
            {"symbol": "ETHUSDT", "quoteVolume": "500000.0"},
            {"symbol": "BADUSDT", "quoteVolume": "0"},
        ]

    monkeypatch.setattr(adapter, "_request_json", fake_request)
    first = adapter.get_24h_quote_volumes()
    second = adapter.get_24h_quote_volumes()
    assert first == {"BTCUSDT": 1000000.5, "ETHUSDT": 500000.0}
    assert second == first
    assert calls == [("/fapi/v1/ticker/24hr", None)]
