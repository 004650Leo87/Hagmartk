from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import threading
import time
from typing import Any, Dict, Iterable, Optional

_logger = logging.getLogger(__name__)
_WS_URL = "wss://fstream.binance.com/ws/!bookTicker"
_BOUNDARY_MS = 5 * 60 * 1000
_CAPTURE_WINDOW_MS = 5000


class BinanceOrbBookTickerCapture:
    """Capture the first observed Bid/Ask event after each M5 boundary.

    Read-only public market data. No authentication, account or order capability.
    """

    def __init__(self) -> None:
        self._symbols: set[str] = set()
        self._captures: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._watchers: Dict[str, Dict[str, Any]] = {}
        self._triggers: Dict[str, Dict[str, Any]] = {}
        self.connection_epoch = 0
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.last_event_at = ""
        self.total_events = 0
        self.total_errors = 0
        self.reconnects = 0

    def update_symbols(self, symbols: Iterable[str]) -> None:
        with self._lock:
            self._symbols = {str(symbol).upper().strip() for symbol in symbols if str(symbol).strip()}

    @staticmethod
    def _quote_from_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if str(message.get("e") or "") != "bookTicker":
            return None
        symbol = str(message.get("s") or "").upper().strip()
        try:
            event_ms = int(message.get("E") or 0)
            bid = float(message.get("b") or 0.0)
            ask = float(message.get("a") or 0.0)
        except (TypeError, ValueError):
            return None
        if not symbol or event_ms <= 0 or bid <= 0 or ask <= 0 or bid > ask:
            return None
        return {
            "symbol": symbol,
            "provider": "BINANCE_USDM_FUTURES",
            "bid": bid,
            "ask": ask,
            "last": 0.0,
            "time": datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc).isoformat(),
            "event_ms": event_ms,
            "source": "BINANCE_FSTREAM_ALL_BOOK_TICKER",
            "read_only": True,
        }
    def ingest_message(self, message: Dict[str, Any]) -> bool:
        quote = self._quote_from_message(message)
        if quote is None:
            return False
        symbol = quote["symbol"]
        event_ms = int(quote["event_ms"])
        boundary_ms = (event_ms // _BOUNDARY_MS) * _BOUNDARY_MS
        with self._condition:
            if self._symbols and symbol not in self._symbols:
                return False
            self._latest[symbol] = dict(quote)
            bucket = self._captures.setdefault(boundary_ms, {})
            bucket.setdefault(symbol, dict(quote))
            for old in sorted(self._captures)[:-4]:
                self._captures.pop(old, None)
            self._evaluate_watch_locked(symbol, quote)
            self.total_events += 1
            self.last_event_at = quote["time"]
            self._condition.notify_all()
        return True

    def _evaluate_watch_locked(self, symbol: str, quote: Dict[str, Any]) -> None:
        watch = self._watchers.get(symbol)
        if not watch or symbol in self._triggers:
            return
        if int(watch["epoch"]) != int(self.connection_epoch):
            self._triggers[symbol] = {"reason": "DATA_GAP", "quote": dict(quote)}
            self._watchers.pop(symbol, None)
            return
        event_time = datetime.fromisoformat(str(quote["time"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        if event_time < watch["entry_time"]:
            return
        bid = float(quote["bid"])
        ask = float(quote["ask"])
        reason = None
        if watch["direction"] == "LONG":
            if bid <= watch["stop"]:
                reason = "STOP"
            elif bid >= watch["target"]:
                reason = "TARGET"
        else:
            if ask >= watch["stop"]:
                reason = "STOP"
            elif ask <= watch["target"]:
                reason = "TARGET"
        if reason is None and event_time >= watch["t120"]:
            reason = "TIME"
        if reason is not None:
            self._triggers[symbol] = {"reason": reason, "quote": dict(quote)}
            self._watchers.pop(symbol, None)

    def register_watch(self, symbol: str, direction: str, stop: float, target: float, t120: datetime, entry_time: datetime) -> None:
        target_symbol = str(symbol).upper().strip()
        with self._condition:
            self._triggers.pop(target_symbol, None)
            self._watchers[target_symbol] = {
                "direction": str(direction).upper(),
                "stop": float(stop),
                "target": float(target),
                "t120": t120.astimezone(timezone.utc),
                "entry_time": entry_time.astimezone(timezone.utc),
                "epoch": int(self.connection_epoch),
            }

    def pop_trigger(self, symbol: str) -> Optional[Dict[str, Any]]:
        target = str(symbol).upper().strip()
        with self._lock:
            row = self._triggers.pop(target, None)
            return dict(row) if row else None

    def unregister_watch(self, symbol: str) -> None:
        target = str(symbol).upper().strip()
        with self._lock:
            self._watchers.pop(target, None)
            self._triggers.pop(target, None)

    def first_quote(self, symbol: str, boundary: datetime) -> Optional[Dict[str, Any]]:
        if boundary.tzinfo is None:
            raise ValueError("boundary must be timezone-aware")
        boundary_ms = int(boundary.astimezone(timezone.utc).timestamp() * 1000)
        with self._lock:
            row = self._captures.get(boundary_ms, {}).get(str(symbol).upper().strip())
            return dict(row) if row else None
    def wait_first_quote(self, symbol: str, boundary: datetime, deadline: datetime) -> Optional[Dict[str, Any]]:
        if boundary.tzinfo is None or deadline.tzinfo is None:
            raise ValueError("boundary/deadline must be timezone-aware")
        target = str(symbol).upper().strip()
        boundary_ms = int(boundary.astimezone(timezone.utc).timestamp() * 1000)
        deadline_utc = deadline.astimezone(timezone.utc)
        with self._condition:
            while True:
                row = self._captures.get(boundary_ms, {}).get(target)
                if row:
                    return dict(row)
                remaining = (deadline_utc - datetime.now(timezone.utc)).total_seconds()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=min(remaining, 0.25))

    def latest_quote(self, symbol: str, max_age_seconds: float = 5.0) -> Optional[Dict[str, Any]]:
        target = str(symbol).upper().strip()
        with self._lock:
            row = self._latest.get(target)
            if not row:
                return None
            event_time = datetime.fromisoformat(str(row["time"]).replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - event_time.astimezone(timezone.utc)).total_seconds() > max_age_seconds:
                return None
            return dict(row)
    def _loop(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                from websockets.sync.client import connect
                with connect(_WS_URL, open_timeout=8, close_timeout=2) as websocket:
                    with self._condition:
                        self.reconnects += 1
                        self.connection_epoch += 1
                        self._condition.notify_all()
                    backoff = 1.0
                    while not self._stop.is_set():
                        raw = websocket.recv(timeout=2)
                        message = json.loads(raw)
                        if isinstance(message, dict):
                            self.ingest_message(message)
            except TimeoutError:
                continue
            except Exception as exc:
                self.total_errors += 1
                _logger.warning("ORB bookTicker stream reconnect: %s", type(exc).__name__)
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2.0, 30.0)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="HAGMARTK-ORB-BookTicker")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=4.0)
        self._thread = None
    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": bool(self._thread and self._thread.is_alive()),
                "symbols": len(self._symbols),
                "last_event_at": self.last_event_at or None,
                "total_events": self.total_events,
                "total_errors": self.total_errors,
                "reconnects": self.reconnects,
                "captured_boundaries": len(self._captures),
                "latest_quotes": len(self._latest),
                "source": "BINANCE_FSTREAM_ALL_BOOK_TICKER",
                "read_only": True,
                "real_order_execution_enabled": False,
            }
