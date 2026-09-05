"""MetaTrader 5 adapter for the Hagmartk Market Engine.

This adapter implements the MarketAdapter interface using the official
`MetaTrader5` Python package. The module avoids importing `MetaTrader5` at
module import time: the library is loaded lazily inside methods so unit tests
can import this module without a live MT5 installation.

Design notes:
- The adapter validates connection state and raises explicit RuntimeError
  with `mt5.last_error()` when available.
- The adapter does not fabricate data — when MT5 returns no data an error is
  raised instead of returning empty or synthetic values.
- The adapter returns UTC timestamps in ISO 8601 format.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from .market_adapter import MarketAdapter
from backend.core.constants import categorize_symbol
from backend.core.exceptions import (
    AdapterUnavailableError,
    AdapterConnectionError,
    AdapterError,
)

# Backwards-compatible alias for older tests and imports
MT5UnavailableError = AdapterUnavailableError


class MT5MarketAdapter(MarketAdapter):
    """Adapter implementation backed by MetaTrader5.

    Methods load the `MetaTrader5` module on demand so the codebase can be
    imported in environments that do not have the native library installed.
    """

    def __init__(self, runtime_scope: Optional[Dict[str, Any]] = None) -> None:
        self._connected = False
        self._runtime_scope = dict(runtime_scope) if runtime_scope is not None else self._load_runtime_scope()
        raw_offset = self._runtime_scope.get("broker_time_offset_hours", 0)
        try:
            offset_hours = float(raw_offset)
        except (TypeError, ValueError) as exc:
            raise AdapterError("Invalid broker_time_offset_hours in MT5 runtime scope") from exc
        if abs(offset_hours) > 14:
            raise AdapterError("broker_time_offset_hours must be between -14 and +14")
        self._broker_time_offset = timedelta(hours=offset_hours)

    @staticmethod
    def _load_runtime_scope() -> Dict[str, Any]:
        scope_path = Path(__file__).resolve().parents[3] / "config" / "mt5_runtime_scope.json"
        if not scope_path.exists():
            return {}
        return json.loads(scope_path.read_text(encoding="utf-8"))

    def _normalize_broker_epoch(self, epoch_seconds: Any) -> datetime:
        raw_dt = datetime.fromtimestamp(float(epoch_seconds), tz=timezone.utc)
        return raw_dt - self._broker_time_offset

    def _to_broker_query_time(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            utc_value = value.replace(tzinfo=timezone.utc)
        else:
            utc_value = value.astimezone(timezone.utc)
        return utc_value + self._broker_time_offset

    def _load_mt5(self):
        try:
            import MetaTrader5 as mt5

            return mt5
        except Exception as error:
            raise AdapterUnavailableError(
                "MetaTrader5 library is not available in this environment",
                name="MetaTrader5",
                details=str(error),
            ) from error

    def connect(self) -> None:
        mt5 = self._load_mt5()

        if self._connected:
            return

        terminal_path = self._runtime_scope.get("terminal_executable")
        initialized = mt5.initialize(path=terminal_path) if terminal_path else mt5.initialize()
        if initialized:
            expected_server = self._runtime_scope.get("server")
            account = mt5.account_info()
            observed_server = getattr(account, "server", None) if account is not None else None
            if expected_server and observed_server != expected_server:
                mt5.shutdown()
                raise AdapterConnectionError(
                    f"MT5 runtime scope mismatch: expected server {expected_server!r}, observed {observed_server!r}"
                )
            self._connected = True
            return

        last = getattr(mt5, "last_error", lambda: None)()
        raise AdapterConnectionError(f"mt5.initialize failed: {last}")

    def disconnect(self) -> None:
        mt5 = self._load_mt5()

        try:
            mt5.shutdown()
        finally:
            self._connected = False

    def get_symbols(self) -> List[Dict[str, Any]]:
        mt5 = self._load_mt5()

        symbols = mt5.symbols_get()

        if symbols is None:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"mt5.symbols_get returned no data: {last}")

        result: List[Dict[str, Any]] = []

        for s in symbols:
            # symbol object shape may vary; we attempt to read common attrs
            name = getattr(s, "name", None) or getattr(s, "_name", None) or str(s)

            info = mt5.symbol_info(name)

            if info is None:
                # fallback minimal representation
                result.append({"name": name, "symbol": name, "category": "OTHER", "broker_path": ""})
                continue

            path = getattr(info, "path", "") or ""
            desc = getattr(info, "description", "") or ""

            result.append(
                {
                    "symbol": name,
                    "name": name,
                    "description": desc,
                    "path": path,
                    "broker_path": path,
                    "category": categorize_symbol(path, name, desc),
                    "visible": bool(getattr(info, "visible", False)),
                    "selected": bool(getattr(info, "selected", False)),
                    "digits": int(getattr(info, "digits", 0)),
                    "point": float(getattr(info, "point", 0.0)),
                    "currency_base": getattr(info, "currency_base", "") or "",
                    "currency_profit": getattr(info, "currency_profit", "") or "",
                    "trade_mode": getattr(info, "trade_mode", None),
                    "spread": getattr(info, "spread", 0),
                    "trade_stops_level": int(getattr(info, "trade_stops_level", 0) or 0),
                    "trade_freeze_level": int(getattr(info, "trade_freeze_level", 0) or 0),
                    "volume_min": float(getattr(info, "volume_min", 0.0)),
                    "volume_max": float(getattr(info, "volume_max", 0.0)),
                    "volume_step": float(getattr(info, "volume_step", 0.0)),
                    "margin_initial": float(getattr(info, "margin_initial", 0.0)),
                    "trade_contract_size": float(getattr(info, "trade_contract_size", 0.0)),
                }
            )

        return result

    def get_supported_timeframes(self) -> Dict[int, str]:
        mt5 = self._load_mt5()

        # Common MT5 timeframe constants mapped to short names
        mapping = {}
        for name in dir(mt5):
            if name.startswith("TIMEFRAME_"):
                val = getattr(mt5, name)
                mapping[val] = name.replace("TIMEFRAME_", "")

        return mapping

    def get_runtime_scope(self) -> Dict[str, Any]:
        return dict(self._runtime_scope)

    def get_connection_info(self) -> Dict[str, Any]:
        mt5 = self._load_mt5()

        info = {}
        try:
            term = getattr(mt5, "terminal_info", lambda: None)()
            if term is not None:
                info["company"] = getattr(term, "company", None)
                info["build"] = getattr(term, "build", None)
            info["connected"] = bool(self._connected)
        except Exception:
            info["connected"] = bool(self._connected)

        return info

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        mt5 = self._load_mt5()

        symbol = symbol.upper().strip()

        info = mt5.symbol_info(symbol)

        if info is None:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"Symbol not found: {symbol} ({last})")

        if not info.visible:
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                last = getattr(mt5, "last_error", lambda: None)()
                raise AdapterError(f"Failed to select symbol '{symbol}': {last}")

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"Failed to get tick for '{symbol}': {last}")

        bid = float(getattr(tick, "bid", 0.0))
        ask = float(getattr(tick, "ask", 0.0))
        last_price = float(getattr(tick, "last", 0.0))

        point = float(getattr(info, "point", 0.0))

        spread_points = 0.0
        if point > 0:
            spread_points = (ask - bid) / point

        raw_tick_time = getattr(tick, "time", 0)
        tick_time = (
            self._normalize_broker_epoch(raw_tick_time).isoformat()
            if raw_tick_time > 0
            else datetime.now(timezone.utc).isoformat()
        )

        return {
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "last": last_price,
            "spread": round(ask - bid, getattr(info, "digits", 0)),
            "spread_points": round(spread_points, 2),
            "digits": int(getattr(info, "digits", 0)),
            "point": point,
            "time": tick_time,
        }

    def get_ticks(
        self,
        symbol: str,
        from_time: datetime,
        to_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Return read-only Bid/Ask ticks normalized to real UTC."""
        mt5 = self._load_mt5()
        symbol = symbol.upper().strip()
        if from_time.tzinfo is None or to_time.tzinfo is None:
            raise ValueError("Tick range requires timezone-aware datetimes")
        if to_time <= from_time:
            raise ValueError("Tick range end must be after start")
        info = mt5.symbol_info(symbol)
        if info is None:
            raise AdapterError(f"Symbol not found: {symbol}")
        if not info.visible and not mt5.symbol_select(symbol, True):
            raise AdapterError(f"Failed to select symbol '{symbol}'")
        rates = mt5.copy_ticks_range(
            symbol,
            self._to_broker_query_time(from_time),
            self._to_broker_query_time(to_time),
            getattr(mt5, "COPY_TICKS_INFO", 0),
        )
        if rates is None:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"No tick data for '{symbol}': {last}")
        ticks: List[Dict[str, Any]] = []
        for row in rates:
            def field(key: str, default: Any = 0) -> Any:
                try:
                    return row[key]
                except Exception:
                    return getattr(row, key, default)
            raw_msc = int(field("time_msc", 0) or 0)
            raw_sec = float(field("time", 0) or 0)
            raw_epoch = raw_msc / 1000.0 if raw_msc > 0 else raw_sec
            timestamp = self._normalize_broker_epoch(raw_epoch).isoformat()
            ticks.append({
                "time": timestamp,
                "bid": float(field("bid", 0.0) or 0.0),
                "ask": float(field("ask", 0.0) or 0.0),
                "last": float(field("last", 0.0) or 0.0),
                "volume": float(field("volume", 0.0) or 0.0),
                "flags": int(field("flags", 0) or 0),
            })
        return ticks

    def get_candles(
        self,
        symbol: str,
        timeframe: Any,
        count: Optional[int] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Return candles for a symbol.

        Parameters:
        - `symbol`: instrument symbol
        - `timeframe`: MT5 timeframe constant (e.g. mt5.TIMEFRAME_M5)
        - `count`: number of most recent candles to return (if provided)
        - `from_time`/`to_time`: datetime range (UTC) to fetch historical candles

        The adapter preserves UTC timestamps and returns full historical data
        when requested. Display layers can still limit how many candles are
        shown to the user, but this method delivers raw historical data.
        """
        mt5 = self._load_mt5()

        symbol = symbol.upper().strip()

        if isinstance(timeframe, str):
            tf_map = {
                "M1": getattr(mt5, "TIMEFRAME_M1", 1),
                "M5": getattr(mt5, "TIMEFRAME_M5", 5),
                "M15": getattr(mt5, "TIMEFRAME_M15", 15),
                "M30": getattr(mt5, "TIMEFRAME_M30", 30),
                "H1": getattr(mt5, "TIMEFRAME_H1", 16385),
                "H2": getattr(mt5, "TIMEFRAME_H2", 16386),
                "H4": getattr(mt5, "TIMEFRAME_H4", 16388),
                "D1": getattr(mt5, "TIMEFRAME_D1", 16408),
                "W1": getattr(mt5, "TIMEFRAME_W1", 32769),
                "MN1": getattr(mt5, "TIMEFRAME_MN1", 49153),
            }
            timeframe = tf_map.get(timeframe.upper().strip(), 15)

        info = mt5.symbol_info(symbol)
        if info is None:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"Symbol not found: {symbol} ({last})")

        if not info.visible:
            selected = mt5.symbol_select(symbol, True)
            if not selected:
                last = getattr(mt5, "last_error", lambda: None)()
                raise AdapterError(f"Failed to select symbol '{symbol}': {last}")

        # Choose fetching method depending on parameters
        rates = None

        if from_time is not None or to_time is not None:
            if from_time is None or to_time is None:
                raise ValueError("Both from_time and to_time must be provided for range queries")

            # MT5 expects datetime objects (aware or naive) — we pass UTC datetimes
            rates = mt5.copy_rates_range(
                symbol, timeframe, self._to_broker_query_time(from_time), self._to_broker_query_time(to_time)
            )
        elif count is not None:
            # fetch last `count` bars
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, int(count))
        else:
            # default: fetch a reasonable amount (e.g. 500) but do not impose
            # a permanent limitation — callers can always request more.
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 500)

        if rates is None or len(rates) == 0:
            last = getattr(mt5, "last_error", lambda: None)()
            raise AdapterError(f"No candle data for '{symbol}': {last}")

        candles: List[Dict[str, Any]] = []

        def _get_field(obj: Any, key: str) -> Any:
            if isinstance(obj, dict):
                return obj.get(key)
            try:
                return obj[key]
            except Exception:
                return getattr(obj, key, None)


        for r in rates:
            time_val = _get_field(r, "time")
            timestamp = (
                self._normalize_broker_epoch(time_val).isoformat()
                if time_val is not None
                else None
            )

            open_v = float(_get_field(r, "open")) if _get_field(r, "open") is not None else None
            high_v = float(_get_field(r, "high")) if _get_field(r, "high") is not None else None
            low_v = float(_get_field(r, "low")) if _get_field(r, "low") is not None else None
            close_v = float(_get_field(r, "close")) if _get_field(r, "close") is not None else None

            tick_volume = int(_get_field(r, "tick_volume")) if _get_field(r, "tick_volume") is not None else 0
            spread = float(_get_field(r, "spread")) if _get_field(r, "spread") is not None else 0.0
            real_volume = float(_get_field(r, "real_volume")) if _get_field(r, "real_volume") is not None else 0.0

            candles.append(
                {
                    "time": timestamp,
                    "open": open_v,
                    "high": high_v,
                    "low": low_v,
                    "close": close_v,
                    "tick_volume": tick_volume,
                    "spread": spread,
                    "real_volume": real_volume,
                }
            )

        return candles
