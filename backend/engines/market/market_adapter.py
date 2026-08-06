"""Market adapter interfaces and test implementations for Hagmartk."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MarketAdapter(ABC):
    """Abstract adapter interface for market data providers.

    The adapter isolates the Market Engine from the underlying market data
    source. It defines the contract that future MT5 or broker adapters must
    implement without introducing direct dependencies into the engine.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the adapter connection to the market source."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the adapter connection and release resources."""

    @abstractmethod
    def get_symbols(self) -> List[str]:
        """Return a list of available market symbols."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Return the latest quote for a given symbol."""

    @abstractmethod
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Return a series of candles for a given symbol and timeframe."""

    @abstractmethod
    def get_supported_timeframes(self) -> Dict[int, str]:
        """Return mapping of supported timeframe constants to human names."""

    @abstractmethod
    def get_connection_info(self) -> Dict[str, Any]:
        """Return diagnostic information about the adapter/connection."""


class MockMarketAdapter(MarketAdapter):
    """Mock implementation of MarketAdapter used for architecture validation.

    This mock adapter allows the Market Engine to be exercised without any
    connection to MetaTrader or external market sources.
    """

    def __init__(self) -> None:
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_symbols(self) -> List[str]:
        return ["EURUSD", "XAUUSD", "BTCUSD"]

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "bid": 1.2345,
            "ask": 1.2348,
            "last": 1.2346,
            "timestamp": "2026-08-05T00:00:00Z",
        }

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "time": f"2026-08-05T00:00:{str(index).zfill(2)}Z",
                "open": 1.2340 + index * 0.0001,
                "high": 1.2345 + index * 0.0001,
                "low": 1.2335 + index * 0.0001,
                "close": 1.2342 + index * 0.0001,
            }
            for index in range(min(limit, 10))
        ]

    def get_supported_timeframes(self) -> Dict[int, str]:
        return {
            1: "M1",
            5: "M5",
            15: "M15",
            30: "M30",
            60: "H1",
            240: "H4",
            1440: "D1",
        }

    def get_connection_info(self) -> Dict[str, Any]:
        return {"name": "mock", "connected": bool(self.connected)}
