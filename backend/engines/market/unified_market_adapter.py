"""Unified read-only market data adapter for HAGMARTK.

Routes each instrument to MT5/Tickmill or Binance USD-M perpetual futures.
No account, credential, trade, withdrawal or order endpoint exists here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core.exceptions import AdapterConnectionError, AdapterError
from .market_adapter import MarketAdapter
from .mt5_market_adapter import MT5MarketAdapter
from .binance_usdm_futures_adapter import (
    BinanceUSDMFuturesMarketAdapter,
    PROVIDER_ID as BINANCE_PROVIDER,
)

MT5_PROVIDER = "MT5_TICKMILL"


class UnifiedMarketAdapter(MarketAdapter):
    def __init__(self) -> None:
        self.mt5 = MT5MarketAdapter()
        self.binance = BinanceUSDMFuturesMarketAdapter()
        self._catalog: List[Dict[str, Any]] = []
        self._provider_by_symbol: Dict[str, str] = {}
        self._connected = False
        self._provider_errors: Dict[str, str] = {}

    def connect(self) -> None:
        connected = 0
        self._provider_errors = {}
        for provider, adapter in ((MT5_PROVIDER, self.mt5), (BINANCE_PROVIDER, self.binance)):
            try:
                adapter.connect()
                connected += 1
            except Exception as exc:
                self._provider_errors[provider] = f"{type(exc).__name__}: {exc}"
        if connected == 0:
            raise AdapterConnectionError("No HAGMARTK market-data provider is available")
        self._connected = True
        self._refresh_catalog()

    def disconnect(self) -> None:
        for adapter in (self.binance, self.mt5):
            try:
                adapter.disconnect()
            except Exception:
                pass
        self._connected = False

    @staticmethod
    def _normalize_mt5_row(row: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(row)
        symbol = str(result.get("symbol") or result.get("name") or "").upper().strip()
        result["symbol"] = symbol
        result["name"] = symbol
        result["provider"] = MT5_PROVIDER
        result["market_type"] = result.get("market_type") or "BROKER_MARKET"
        result["instrument_id"] = f"{MT5_PROVIDER}:{symbol}"
        result["read_only"] = True
        result["real_order_execution_enabled"] = False
        return result

    def _refresh_catalog(self) -> None:
        rows: List[Dict[str, Any]] = []
        provider_map: Dict[str, str] = {}
        try:
            for raw in self.mt5.get_symbols():
                row = self._normalize_mt5_row(raw)
                symbol = row["symbol"]
                if symbol:
                    rows.append(row)
                    provider_map[symbol] = MT5_PROVIDER
        except Exception as exc:
            self._provider_errors[MT5_PROVIDER] = f"{type(exc).__name__}: {exc}"
        try:
            for raw in self.binance.get_symbols():
                row = dict(raw)
                symbol = str(row.get("symbol") or "").upper().strip()
                if not symbol:
                    continue
                if symbol in provider_map:
                    continue
                rows.append(row)
                provider_map[symbol] = BINANCE_PROVIDER
        except Exception as exc:
            self._provider_errors[BINANCE_PROVIDER] = f"{type(exc).__name__}: {exc}"
        if not rows:
            raise AdapterError("Unified market catalog is empty")
        self._catalog = rows
        self._provider_by_symbol = provider_map

    def get_symbols(self) -> List[Dict[str, Any]]:
        if not self._catalog:
            self._refresh_catalog()
        return [dict(row) for row in self._catalog]

    def provider_for_symbol(self, symbol: str) -> str:
        target = symbol.upper().strip()
        if not self._provider_by_symbol:
            self._refresh_catalog()
        provider = self._provider_by_symbol.get(target)
        if provider is None:
            raise AdapterError(f"Unified symbol not found: {target}")
        return provider

    def _adapter_for_symbol(self, symbol: str):
        provider = self.provider_for_symbol(symbol)
        return self.binance if provider == BINANCE_PROVIDER else self.mt5

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        quote = dict(self._adapter_for_symbol(symbol).get_quote(symbol))
        quote.setdefault("provider", self.provider_for_symbol(symbol))
        return quote

    def get_candles(
        self,
        symbol: str,
        timeframe: Any,
        limit: Optional[int] = None,
        count: Optional[int] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        adapter = self._adapter_for_symbol(symbol)
        requested = count if count is not None else limit
        return adapter.get_candles(
            symbol,
            timeframe,
            count=requested,
            from_time=from_time,
            to_time=to_time,
        )

    def get_ticks(self, symbol: str, from_time: datetime, to_time: datetime) -> List[Dict[str, Any]]:
        provider = self.provider_for_symbol(symbol)
        if provider == BINANCE_PROVIDER:
            # Binance public REST does not expose historical Bid/Ask book ticks.
            # Prospective Cycle Theory still processes current sampled Bid/Ask;
            # missing intervals are never fabricated.
            return []
        return self.mt5.get_ticks(symbol, from_time, to_time)

    def get_supported_timeframes(self) -> Dict[int, str]:
        result = dict(self.mt5.get_supported_timeframes())
        result.update(self.binance.get_supported_timeframes())
        return result

    def get_runtime_scope(self) -> Dict[str, Any]:
        scope = self.mt5.get_runtime_scope()
        return {**scope, "market_data_mode": "UNIFIED_READ_ONLY"}

    def get_connection_info(self) -> Dict[str, Any]:
        return {
            "name": "HAGMARTK_UNIFIED_MARKET_DATA",
            "connected": bool(self._connected),
            "read_only": True,
            "real_order_execution_enabled": False,
            "providers": {
                MT5_PROVIDER: self.mt5.get_connection_info(),
                BINANCE_PROVIDER: self.binance.get_connection_info(),
            },
            "provider_errors": dict(self._provider_errors),
        }

    def get_quotes_bulk(self) -> Dict[str, Dict[str, Any]]:
        """Bulk snapshot optimized for wide prospective scanners."""
        result: Dict[str, Dict[str, Any]] = {}
        try:
            all_binance = self.binance.get_book_tickers()
            allowed = {
                symbol for symbol, provider in self._provider_by_symbol.items()
                if provider == BINANCE_PROVIDER
            }
            result.update({symbol: quote for symbol, quote in all_binance.items() if symbol in allowed})
        except Exception as exc:
            self._provider_errors[BINANCE_PROVIDER] = f"{type(exc).__name__}: {exc}"
        mt5_symbols = [
            row["symbol"] for row in self.get_symbols()
            if row.get("provider") == MT5_PROVIDER
        ]
        for symbol in mt5_symbols:
            try:
                quote = dict(self.mt5.get_quote(symbol))
                quote["provider"] = MT5_PROVIDER
                result[symbol] = quote
            except Exception:
                continue
        return result
