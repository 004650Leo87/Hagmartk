import pytest

from backend.engines.market.normalized_market_data import MarketDataProvenance, normalize_candle


def prov(provider="mt5", volume_kind="tick_volume"):
    return MarketDataProvenance(provider, "ANY_SYMBOL", "M15", volume_kind)


def test_mt5_tick_volume_can_be_normalized_without_strategy_symbol_rules():
    c = {"time": "2026-09-02T12:00:00+00:00", "open": 10, "high": 12, "low": 9,
         "close": 11, "tick_volume": 321}
    out = normalize_candle(candle=c, provenance=prov(), volume_field="tick_volume")
    assert out.volume == 321
    assert out.provenance.symbol == "ANY_SYMBOL"


def test_exchange_volume_can_use_same_contract_for_future_public_api_adapter():
    c = {"time": "2026-09-02T12:00:00Z", "open": 50000, "high": 51000, "low": 49000,
         "close": 50500, "base_volume": 42.5}
    out = normalize_candle(candle=c, provenance=prov("exchange_api", "exchange_volume"),
                           volume_field="base_volume")
    assert out.volume == 42.5
    assert out.provenance.provider == "exchange_api"


def test_rejects_invalid_ohlc_geometry():
    c = {"time": "t", "open": 10, "high": 9, "low": 8, "close": 11, "volume": 1}
    with pytest.raises(ValueError, match="invalid OHLC geometry"):
        normalize_candle(candle=c, provenance=prov(), volume_field="volume")


def test_rejects_missing_or_negative_volume():
    base = {"time": "t", "open": 10, "high": 11, "low": 9, "close": 10}
    with pytest.raises(ValueError, match="missing market-data fields"):
        normalize_candle(candle=base, provenance=prov(), volume_field="volume")
    with pytest.raises(ValueError, match="volume must be non-negative"):
        normalize_candle(candle={**base, "volume": -1}, provenance=prov(), volume_field="volume")
