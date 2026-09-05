"""Adapter contract tests for MT5MarketAdapter and MockMarketAdapter.

These tests do not require a live MT5 terminal. The MT5 adapter tests mock the
`MetaTrader5` module to validate behavior and error handling.
"""

import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from backend.engines.market.market_adapter import MockMarketAdapter
from backend.engines.market.mt5_market_adapter import MT5MarketAdapter, MT5UnavailableError


def test_mock_adapter_basic_contract():
    adapter = MockMarketAdapter()

    adapter.connect()
    symbols = adapter.get_symbols()
    assert isinstance(symbols, list) and len(symbols) >= 1

    quote = adapter.get_quote(symbols[0])
    assert quote.get("symbol") == symbols[0]

    candles = adapter.get_candles(symbols[0], "M5", limit=5)
    assert isinstance(candles, list)

    adapter.disconnect()


def make_fake_mt5_module():
    fake = types.SimpleNamespace()

    # last_error returns (code, message)
    fake._last_error = (0, "ok")

    def last_error():
        return fake._last_error

    def initialize(*args, **kwargs):
        return True

    def shutdown():
        return True

    def account_info():
        return types.SimpleNamespace(server="Tickmill-Live")

    def symbols_get():
        # return objects with a `name` attribute
        return [types.SimpleNamespace(name="EURUSD"), types.SimpleNamespace(name="XAUUSD")]

    def symbol_info(name):
        return types.SimpleNamespace(
            name=name,
            description=f"{name} description",
            path="Forex/major",
            visible=True,
            selected=True,
            digits=5,
            point=0.00001,
            currency_base="USD",
            currency_profit="USD",
            trade_mode=0,
        )

    def symbol_info_tick(name):
        return types.SimpleNamespace(bid=1.1, ask=1.1003, last=1.1002, time=1620000000)

    def symbol_select(name, enable):
        return True

    def copy_rates_from_pos(symbol, timeframe, pos, count):
        # return list-like of dicts
        out = []
        for i in range(count):
            out.append({
                "time": 1620000000 + i,
                "open": 1.0 + i * 0.1,
                "high": 1.05 + i * 0.1,
                "low": 0.95 + i * 0.1,
                "close": 1.02 + i * 0.1,
                "tick_volume": 100 + i,
                "spread": 1,
                "real_volume": 10 + i,
            })
        return out

    def copy_rates_range(symbol, timeframe, from_time, to_time):
        fake.last_range_args = (from_time, to_time)
        # return a small range based on seconds
        seconds = int((to_time - from_time).total_seconds())
        n = min(10, max(1, seconds // 60))
        return copy_rates_from_pos(symbol, timeframe, 0, n)

    def copy_ticks_range(symbol, from_time, to_time, flags):
        fake.last_tick_range_args = (from_time, to_time, flags)
        base = 1620000000
        return [
            {"time": base, "time_msc": base * 1000 + 125, "bid": 1.1, "ask": 1.1002, "last": 1.1001, "volume": 1.0, "flags": 2},
            {"time": base, "time_msc": base * 1000 + 500, "bid": 1.1001, "ask": 1.1003, "last": 1.1002, "volume": 2.0, "flags": 2},
        ]

    fake.last_error = last_error
    fake.initialize = initialize
    fake.shutdown = shutdown
    fake.account_info = account_info
    fake.symbols_get = symbols_get
    fake.symbol_info = symbol_info
    fake.symbol_info_tick = symbol_info_tick
    fake.symbol_select = symbol_select
    fake.copy_rates_from_pos = copy_rates_from_pos
    fake.copy_rates_range = copy_rates_range
    fake.copy_ticks_range = copy_ticks_range
    fake.COPY_TICKS_INFO = 2

    return fake


def test_mt5_adapter_with_mocked_mt5(monkeypatch):
    fake_mt5 = make_fake_mt5_module()

    # inject fake module
    sys.modules["MetaTrader5"] = fake_mt5

    adapter = MT5MarketAdapter(runtime_scope={"server": "Tickmill-Live"})

    # connection
    adapter.connect()

    symbols = adapter.get_symbols()
    assert isinstance(symbols, list)
    assert any(s.get("name") == "EURUSD" for s in symbols)

    quote = adapter.get_quote("EURUSD")
    assert quote["symbol"] == "EURUSD"
    assert quote["time"] == datetime.fromtimestamp(1620000000, tz=timezone.utc).isoformat()

    # by count
    candles = adapter.get_candles("EURUSD", 5, count=3)
    assert isinstance(candles, list) and len(candles) == 3
    assert candles[0]["time"] == datetime.fromtimestamp(1620000000, tz=timezone.utc).isoformat()

    # by range
    now = datetime.now(timezone.utc)
    then = now - timedelta(minutes=10)
    candles_range = adapter.get_candles("EURUSD", 5, from_time=then, to_time=now)
    assert isinstance(candles_range, list)

    adapter.disconnect()

    # cleanup fake
    del sys.modules["MetaTrader5"]


def test_mt5_adapter_raises_when_mt5_missing():
    # ensure MetaTrader5 not in sys.modules
    if "MetaTrader5" in sys.modules:
        del sys.modules["MetaTrader5"]
    # If MetaTrader5 is installed in the environment the import will succeed
    # and raising an error is not expected. In that case skip this assertion
    # to make the test environment-agnostic.
    try:
        import MetaTrader5  # type: ignore
    except Exception:
        with pytest.raises(MT5UnavailableError):
            MT5MarketAdapter()._load_mt5()
    else:
        pytest.skip("MetaTrader5 is installed in the environment; skipping missing-module assertion")


def test_mt5_adapter_normalizes_configured_broker_time_offset(monkeypatch):
    fake_mt5 = make_fake_mt5_module()
    sys.modules["MetaTrader5"] = fake_mt5

    adapter = MT5MarketAdapter(
        runtime_scope={"server": "Tickmill-Live", "broker_time_offset_hours": 3}
    )
    adapter.connect()

    expected = datetime.fromtimestamp(1620000000, tz=timezone.utc) - timedelta(hours=3)
    assert adapter.get_quote("EURUSD")["time"] == expected.isoformat()
    assert adapter.get_candles("EURUSD", 5, count=1)[0]["time"] == expected.isoformat()

    start = datetime(2026, 9, 3, 20, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=10)
    adapter.get_candles("EURUSD", 5, from_time=start, to_time=end)
    sent_start, sent_end = fake_mt5.last_range_args
    assert sent_start == start + timedelta(hours=3)
    assert sent_end == end + timedelta(hours=3)

    adapter.disconnect()
    del sys.modules["MetaTrader5"]


def test_mt5_adapter_get_ticks_uses_scoped_clock_and_preserves_subsecond_order():
    fake_mt5 = make_fake_mt5_module()
    sys.modules["MetaTrader5"] = fake_mt5
    adapter = MT5MarketAdapter(
        runtime_scope={"server": "Tickmill-Live", "broker_time_offset_hours": 3}
    )
    adapter.connect()
    start = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=1)

    ticks = adapter.get_ticks("EURUSD", start, end)

    sent_start, sent_end, flags = fake_mt5.last_tick_range_args
    assert sent_start == start + timedelta(hours=3)
    assert sent_end == end + timedelta(hours=3)
    assert flags == fake_mt5.COPY_TICKS_INFO
    assert len(ticks) == 2
    assert ticks[0]["time"] < ticks[1]["time"]
    adapter.disconnect()
    del sys.modules["MetaTrader5"]
