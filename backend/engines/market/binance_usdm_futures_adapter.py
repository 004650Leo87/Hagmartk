"""Read-only Binance USDⓈ-M perpetual futures market-data adapter.

Public endpoints only: no API key, account access or trade endpoint exists here.
The adapter normalizes Binance futures data to the HAGMARTK market contract.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.core.exceptions import AdapterConnectionError, AdapterError
from .market_adapter import MarketAdapter


REST_BASE = "https://fapi.binance.com"
PROVIDER_ID = "BINANCE_USDM_FUTURES"
MARKET_TYPE = "PERPETUAL_FUTURES"
_INTERVALS = {
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h",
    "H12": "12h", "D1": "1d", "D3": "3d", "W1": "1w", "MN1": "1M",
}
_CODE_TO_NAME = {
    1: "M1", 3: "M3", 5: "M5", 15: "M15", 30: "M30",
    16385: "H1", 16386: "H2", 16388: "H4", 16390: "H6",
    16392: "H8", 16396: "H12", 16408: "D1", 32769: "W1", 49153: "MN1",
}


class BinanceUSDMFuturesMarketAdapter(MarketAdapter):
    def __init__(self, timeout_seconds: float = 8.0, exchange_cache_seconds: float = 60.0) -> None:
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 20.0))
        self.exchange_cache_seconds = max(5.0, float(exchange_cache_seconds))
        self._connected = False
        self._exchange_cache: Optional[Dict[str, Any]] = None
        self._exchange_cache_at = 0.0
        self._lock = threading.RLock()
    def _request_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{REST_BASE}{path}" + (f"?{query}" if query else "")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HAGMARTK-MF/1.0"})
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    if int(response.status) != 200:
                        raise AdapterError(f"Binance USD-M HTTP {response.status}")
                    return json.loads(response.read().decode("utf-8") or "null")
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.15 * (2 ** attempt))
        raise AdapterError(f"Binance USD-M request failed: {type(last_error).__name__}") from last_error

    def connect(self) -> None:
        try:
            self._request_json("/fapi/v1/ping")
            self._connected = True
        except Exception as exc:
            raise AdapterConnectionError(f"Binance USD-M connectivity failed: {exc}") from exc

    def disconnect(self) -> None:
        self._connected = False
    def _exchange_info(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            if self._exchange_cache is not None and (now - self._exchange_cache_at) < self.exchange_cache_seconds:
                return self._exchange_cache
            payload = self._request_json("/fapi/v1/exchangeInfo")
            if not isinstance(payload, dict):
                raise AdapterError("Binance USD-M exchangeInfo returned invalid payload")
            self._exchange_cache = payload
            self._exchange_cache_at = now
            return payload

    @staticmethod
    def _filter_value(filters: List[Dict[str, Any]], filter_type: str, key: str, default: Any = 0) -> Any:
        for item in filters:
            if item.get("filterType") == filter_type:
                return item.get(key, default)
        return default

    def get_symbols(self) -> List[Dict[str, Any]]:
        info = self._exchange_info()
        result: List[Dict[str, Any]] = []
        for item in info.get("symbols", []):
            if item.get("status") != "TRADING" or item.get("contractType") != "PERPETUAL":
                continue
            filters = item.get("filters") or []
            symbol = str(item.get("symbol") or "").upper()
            result.append({
                "symbol": symbol, "name": symbol,
                "description": f"{item.get('baseAsset', '')}/{item.get('quoteAsset', '')} Perpetual Futures",
                "path": f"Binance USD-M/{item.get('quoteAsset', '')}/PERPETUAL",
                "broker_path": f"Binance USD-M/{item.get('quoteAsset', '')}/PERPETUAL",
                "category": "CRYPTO", "provider": PROVIDER_ID, "market_type": MARKET_TYPE,
                "instrument_id": f"{PROVIDER_ID}:{symbol}", "visible": True, "selected": True,
                "digits": int(item.get("pricePrecision") or 0),
                "point": float(self._filter_value(filters, "PRICE_FILTER", "tickSize", 0) or 0),
                "currency_base": item.get("baseAsset") or "", "currency_profit": item.get("quoteAsset") or "",
                "trade_mode": "MARKET_DATA_ONLY", "spread": None,
                "trade_stops_level": 0, "trade_freeze_level": 0,
                "volume_min": float(self._filter_value(filters, "LOT_SIZE", "minQty", 0) or 0),
                "volume_max": float(self._filter_value(filters, "LOT_SIZE", "maxQty", 0) or 0),
                "volume_step": float(self._filter_value(filters, "LOT_SIZE", "stepSize", 0) or 0),
                "margin_initial": 0.0, "trade_contract_size": 1.0,
                "contract_type": "PERPETUAL", "settle_asset": item.get("marginAsset") or "",
                "read_only": True, "real_order_execution_enabled": False,
            })
        return result

    def has_symbol(self, symbol: str) -> bool:
        target = symbol.upper().strip()
        return any(item["symbol"] == target for item in self.get_symbols())

    def get_supported_timeframes(self) -> Dict[int, str]:
        result: Dict[int, str] = {}
        for code, name in _CODE_TO_NAME.items():
            if name in _INTERVALS:
                result[code] = name
        return result
    def get_connection_info(self) -> Dict[str, Any]:
        return {
            "name": PROVIDER_ID,
            "provider": PROVIDER_ID,
            "market_type": MARKET_TYPE,
            "connected": bool(self._connected),
            "read_only": True,
            "authentication": "NONE",
            "real_order_execution_enabled": False,
        }

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper().strip()
        if not self.has_symbol(symbol):
            raise AdapterError(f"Binance USD-M perpetual symbol not found: {symbol}")
        meta = next(item for item in self.get_symbols() if item["symbol"] == symbol)
        book = self._request_json("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        last = self._request_json("/fapi/v1/ticker/price", {"symbol": symbol})
        bid = float(book.get("bidPrice") or 0)
        ask = float(book.get("askPrice") or 0)
        last_price = float(last.get("price") or 0)
        digits = int(meta.get("digits") or 0)
        point = float(meta.get("point") or 0)
        spread = ask - bid
        event_ms = int(book.get("time") or last.get("time") or 0)
        event_time = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc).isoformat() if event_ms else datetime.now(timezone.utc).isoformat()
        return {
            "symbol": symbol, "provider": PROVIDER_ID, "market_type": MARKET_TYPE,
            "bid": bid, "ask": ask, "last": last_price,
            "spread": round(spread, digits),
            "spread_points": round(spread / point, 2) if point > 0 else None,
            "digits": digits, "point": point,
            "time": event_time, "read_only": True,
        }
    @staticmethod
    def _interval(timeframe: Any) -> str:
        if isinstance(timeframe, int):
            timeframe = _CODE_TO_NAME.get(timeframe)
        name = str(timeframe or "M5").upper().strip()
        interval = _INTERVALS.get(name)
        if interval is None:
            raise ValueError(f"Unsupported Binance USD-M timeframe: {timeframe}")
        return interval

    def get_candles(
        self,
        symbol: str,
        timeframe: Any,
        limit: Optional[int] = None,
        count: Optional[int] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        symbol = symbol.upper().strip()
        if not self.has_symbol(symbol):
            raise AdapterError(f"Binance USD-M perpetual symbol not found: {symbol}")
        requested = int(count if count is not None else limit if limit is not None else 500)
        if requested < 1 or requested > 1500:
            raise ValueError("Binance USD-M candle count must be between 1 and 1500")
        params: Dict[str, Any] = {"symbol": symbol, "interval": self._interval(timeframe), "limit": requested}
        if from_time is not None:
            if from_time.tzinfo is None:
                raise ValueError("from_time must be timezone-aware")
            params["startTime"] = int(from_time.astimezone(timezone.utc).timestamp() * 1000)
        if to_time is not None:
            if to_time.tzinfo is None:
                raise ValueError("to_time must be timezone-aware")
            params["endTime"] = int(to_time.astimezone(timezone.utc).timestamp() * 1000)
        rows = self._request_json("/fapi/v1/klines", params)
        if not isinstance(rows, list) or not rows:
            raise AdapterError(f"No Binance USD-M candles for {symbol}")
        candles: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 11:
                continue
            open_ms = int(row[0])
            close_ms = int(row[6])
            candles.append({
                "time": datetime.fromtimestamp(open_ms / 1000, tz=timezone.utc).isoformat(),
                "close_time": datetime.fromtimestamp(close_ms / 1000, tz=timezone.utc).isoformat(),
                "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]),
                "tick_volume": int(row[8]), "spread": 0.0, "real_volume": float(row[5]),
                "volume": float(row[5]), "quote_volume": float(row[7]),
                "trades": int(row[8]), "taker_buy_volume": float(row[9]),
                "taker_buy_quote_volume": float(row[10]),
                "provider": PROVIDER_ID, "market_type": MARKET_TYPE,
            })
        if not candles:
            raise AdapterError(f"Invalid Binance USD-M candle payload for {symbol}")
        return candles

    def get_mark_price(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper().strip()
        payload = self._request_json("/fapi/v1/premiumIndex", {"symbol": symbol})
        return {
            "symbol": symbol, "provider": PROVIDER_ID,
            "mark_price": float(payload.get("markPrice") or 0),
            "index_price": float(payload.get("indexPrice") or 0),
            "last_funding_rate": float(payload.get("lastFundingRate") or 0),
            "next_funding_time": int(payload.get("nextFundingTime") or 0),
        }
