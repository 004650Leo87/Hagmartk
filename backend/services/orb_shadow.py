from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import threading
import time
from typing import Any, Dict, Optional

from backend.strategies.orb.config import DEFAULT_ORB_CONFIG, ORB_V1_CONFIG_HASH
from backend.strategies.orb.core import (
    build_opening_range,
    evaluate_signal,
    finalize_trade_levels,
    resolve_session_window,
    size_linear_entry,
)
from backend.strategies.orb.models import Candle, Direction, OpeningRange, Quote, SessionState
from backend.strategies.orb.profiles import (
    OrbProfileResolution,
    load_orb_profile_policy,
    resolve_orb_universe,
)
from backend.services.orb_shadow_store import OrbShadowStore
from backend.services.orb_binance_capture import BinanceOrbBookTickerCapture
from backend.services.telegram_notifier import TelegramNotifier

_logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _s(value: Any) -> str:
    return "" if value is None else str(value)


class OrbProspectiveScanner:
    """Prospective PAPER observer for the frozen ORB v1 contract.

    Current release resolves only explicit provider/session templates. It never
    transmits broker orders. Market entry/exit prices are PAPER calculations.
    """

    def __init__(
        self,
        store: Optional[OrbShadowStore] = None,
        notifier: Optional[TelegramNotifier] = None,
        max_workers: int = 96,
    ) -> None:
        self.store = store or OrbShadowStore()
        self.notifier = notifier or TelegramNotifier()
        self.capture = BinanceOrbBookTickerCapture()
        self.policy = load_orb_profile_policy()
        self.max_workers = max(8, min(int(max_workers), 128))
        self.adapter: Any = None
        self.started_at = _now_utc()
        self.last_cycle_at = ""
        self.total_cycles = 0
        self.total_errors = 0
        self.total_bar_batches = 0
        self._eligible: Dict[str, tuple[Dict[str, Any], OrbProfileResolution]] = {}
        self._reasons: Dict[str, int] = {}
        self._catalog_total = 0
        self._prepared_date: Optional[date] = None
        self._last_boundary: Optional[datetime] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def refresh_universe(self) -> int:
        rows = [dict(row) for row in self.adapter.get_symbols()]
        resolved, reasons = resolve_orb_universe(rows, self.policy)
        self._eligible = {str(row["symbol"]).upper(): (row, resolution) for row, resolution in resolved}
        self._reasons = reasons
        self._catalog_total = len(rows)
        self.capture.update_symbols(self._eligible.keys())
        return len(self._eligible)

    def _session_for(self, resolution: OrbProfileResolution, local_date: date):
        assert resolution.profile is not None
        return resolve_session_window(local_date, resolution.profile)

    def _base_session_row(
        self,
        symbol: str,
        resolution: OrbProfileResolution,
        local_date: date,
        now: datetime,
    ) -> Dict[str, Any]:
        profile = resolution.profile
        assert profile is not None
        session = self._session_for(resolution, local_date)
        return {
            "session_id": session.session_id,
            "strategy_id": DEFAULT_ORB_CONFIG.strategy_id,
            "version": DEFAULT_ORB_CONFIG.strategy_version,
            "config_hash": ORB_V1_CONFIG_HASH,
            "profile_id": resolution.profile_id,
            "profile_hash": resolution.profile_hash,
            "symbol": symbol,
            "provider": profile.provider,
            "account_currency": profile.account_currency,
            "t0": session.t0.isoformat(),
            "t60": session.t60.isoformat(),
            "t120": session.t120.isoformat(),
            "state": SessionState.BUILD_RANGE.value,
            "opportunity_consumed": 0,
            "range_high": None,
            "range_low": None,
            "signal_id": None,
            "direction": None,
            "signal_time": None,
            "entry_time": None,
            "entry_price": None,
            "quantity": None,
            "stop_price": None,
            "target_price": None,
            "risk_cash": None,
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "costs_cash": None,
            "pnl_gross": None,
            "pnl_net": None,
            "r_multiple": None,
            "last_evaluated_close": None,
            "rejection_reason": None,
            "data_quality_flags": "[]",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

    def _prepare_current_date(self, now: datetime) -> None:
        if self._prepared_date == now.date():
            return
        self._prepared_date = now.date()
        for symbol, (_, resolution) in self._eligible.items():
            try:
                session = self._session_for(resolution, now.date())
            except Exception:
                continue
            existing = self.store.get_session(session.session_id)
            if existing is not None:
                continue
            # A scanner that starts after range formation must not reconstruct
            # and trade a historical signal from earlier in the same session.
            if now >= session.t0 + timedelta(minutes=DEFAULT_ORB_CONFIG.opening_range_minutes):
                continue
            self.store.upsert_session(self._base_session_row(symbol, resolution, now.date(), now))

    @staticmethod
    def _candle_from_row(row: Dict[str, Any]) -> Candle:
        open_time = _parse_iso(str(row["time"]))
        return Candle(
            open_time=open_time,
            close_time=open_time + timedelta(minutes=5),
            open=Decimal(str(row["open"])),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
            close=Decimal(str(row["close"])),
        )

    def _fetch_candles_for_boundary(self, symbol: str, boundary: datetime, count: int) -> list[Candle]:
        rows = self.adapter.get_candles(symbol, "M5", count=count)
        candles = [self._candle_from_row(dict(row)) for row in rows]
        return [candle for candle in candles if candle.close_time <= boundary]

    def _event(self, row: Dict[str, Any], event_type: str, event_time: datetime, payload: Dict[str, Any], notify: bool = True) -> None:
        event_id = f"{row['session_id']}:{event_type}:{payload.get('signal_id') or payload.get('exit_reason') or event_time.isoformat()}"
        body = {
            "strategy_id": DEFAULT_ORB_CONFIG.strategy_id,
            "version": DEFAULT_ORB_CONFIG.strategy_version,
            "config_hash": ORB_V1_CONFIG_HASH,
            "profile_id": row["profile_id"],
            "profile_hash": row["profile_hash"],
            "symbol": row["symbol"],
            "provider": row["provider"],
            "event_time": event_time.isoformat(),
            "paper_only": True,
            "real_order_execution_enabled": False,
            "range_high": row.get("range_high"),
            "range_low": row.get("range_low"),
            "t0": row.get("t0"),
            "signal_time": row.get("signal_time"),
            **payload,
        }
        inserted = self.store.append_event(
            event_id=event_id,
            session_id=row["session_id"],
            symbol=row["symbol"],
            event_type=event_type,
            event_time=event_time.isoformat(),
            payload=body,
            created_at=_now_utc().isoformat(),
        )
        if inserted and notify:
            try:
                self.notifier.notify_orb_async(event_type, body)
            except Exception:
                _logger.exception("ORB Telegram notification failed")

    def _mark_rejected(self, row: Dict[str, Any], reason: str, now: datetime) -> None:
        row["state"] = SessionState.SKIPPED.value
        row["rejection_reason"] = reason
        row["updated_at"] = now.isoformat()
        self.store.upsert_session(row)
        self._event(row, "ENTRY_REJECTED", now, {"reason": reason, "signal_id": row.get("signal_id")})

    def _build_ranges(self, boundary: datetime) -> None:
        if not self._eligible:
            return
        sample_resolution = next(iter(self._eligible.values()))[1]
        session = self._session_for(sample_resolution, boundary.date())
        sessions = {row["symbol"]: row for row in self.store.sessions_for_t0(session.t0.isoformat())}
        targets = [symbol for symbol, row in sessions.items() if row["state"] == SessionState.BUILD_RANGE.value]
        if not targets:
            return
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(self._fetch_candles_for_boundary, symbol, boundary, 4): symbol
                for symbol in targets
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                row = sessions[symbol]
                try:
                    candles = future.result()
                    resolution = self._eligible[symbol][1]
                    profile = resolution.profile
                    assert profile is not None
                    session = self._session_for(resolution, boundary.date())
                    opening = build_opening_range(candles, session, profile)
                    row["range_high"] = _s(opening.high)
                    row["range_low"] = _s(opening.low)
                    row["state"] = SessionState.WAIT_SIGNAL.value
                    row["last_evaluated_close"] = boundary.isoformat()
                    row["updated_at"] = _now_utc().isoformat()
                    self.store.upsert_session(row)
                    self._event(
                        row, "RANGE_FROZEN", boundary,
                        {"H_OR": _s(opening.high), "L_OR": _s(opening.low)},
                        notify=False,
                    )
                except Exception as exc:
                    row["state"] = SessionState.SKIPPED.value
                    row["rejection_reason"] = str(exc)
                    row["updated_at"] = _now_utc().isoformat()
                    self.store.upsert_session(row)

    def _estimated_funding_cost_per_unit(self, symbol: str, signal_time: datetime, t120: datetime, profile) -> Decimal:
        binance = getattr(self.adapter, "binance", None)
        if binance is None or not hasattr(binance, "get_mark_price"):
            raise ValueError("FUNDING_MODEL_UNAVAILABLE")
        info = binance.get_mark_price(symbol)
        next_ms = int(info.get("next_funding_time") or 0)
        if next_ms <= 0:
            raise ValueError("FUNDING_SCHEDULE_UNKNOWN")
        next_funding = datetime.fromtimestamp(next_ms / 1000, tz=timezone.utc)
        if not (signal_time < next_funding <= t120):
            return Decimal("0")
        rate = abs(Decimal(str(info.get("last_funding_rate") or 0)))
        mark = abs(Decimal(str(info.get("mark_price") or 0)))
        if mark <= 0:
            raise ValueError("FUNDING_MARK_PRICE_UNKNOWN")
        return mark * profile.point_value * rate

    def _realized_funding_cash(self, row: Dict[str, Any], exit_time: datetime, profile) -> Decimal:
        binance = getattr(self.adapter, "binance", None)
        if binance is None or not hasattr(binance, "get_funding_rates"):
            raise ValueError("FUNDING_HISTORY_UNAVAILABLE")
        entry_time = _parse_iso(str(row["entry_time"]))
        rates = binance.get_funding_rates(str(row["symbol"]), entry_time, exit_time)
        direction = Direction(str(row["direction"]))
        quantity = Decimal(str(row["quantity"]))
        total = Decimal("0")
        for item in rates:
            mark = Decimal(str(item.get("mark_price") or 0))
            rate = Decimal(str(item.get("funding_rate") or 0))
            if mark <= 0:
                raise ValueError("FUNDING_HISTORY_MARK_PRICE_UNKNOWN")
            total += direction.sign * quantity * profile.point_value * mark * rate
        return total

    def _enter_paper(
        self,
        row: Dict[str, Any],
        resolution: OrbProfileResolution,
        opening: OpeningRange,
        signal,
        session,
    ) -> None:
        now = _now_utc()
        # The first opportunity is persisted before any quote/order-like action.
        row["opportunity_consumed"] = 1
        row["signal_id"] = signal.signal_id
        row["direction"] = signal.direction.value
        row["signal_time"] = signal.t_signal.isoformat()
        row["state"] = SessionState.ENTRY_PENDING.value
        row["updated_at"] = now.isoformat()
        self.store.upsert_session(row)
        self._event(row, "SIGNAL", signal.t_signal, {
            "signal_id": signal.signal_id,
            "direction": signal.direction.value,
            "t_signal": signal.t_signal.isoformat(),
            "H_OR": _s(opening.high),
            "L_OR": _s(opening.low),
        })

        try:
            profile = resolution.profile
            assert profile is not None
            deadline = min(
                signal.t_signal + timedelta(milliseconds=DEFAULT_ORB_CONFIG.entry_quote_ttl_ms),
                session.t60,
            )
            quote_raw = self.capture.wait_first_quote(row["symbol"], signal.t_signal, deadline)
            if quote_raw is None:
                raise ValueError("ENTRY_EXPIRED")
            quote = Quote(
                time=_parse_iso(str(quote_raw["time"])),
                bid=Decimal(str(quote_raw["bid"])),
                ask=Decimal(str(quote_raw["ask"])),
            )
            funding_estimate = self._estimated_funding_cost_per_unit(
                row["symbol"], signal.t_signal, session.t120, profile
            )
            sizing_profile = replace(profile, fees_roundtrip_per_unit=funding_estimate)
            preflight = size_linear_entry(signal, quote, session, opening, sizing_profile)
            levels = finalize_trade_levels(
                signal.direction, preflight.quantity, preflight.entry_model, preflight.stop, profile
            )
            row["entry_time"] = quote.time.isoformat()
            row["entry_price"] = _s(levels.entry)
            row["quantity"] = _s(levels.quantity)
            row["stop_price"] = _s(levels.stop)
            row["target_price"] = _s(levels.target)
            row["risk_cash"] = _s(levels.risk_cash)
            row["state"] = SessionState.OPEN.value
            row["updated_at"] = _now_utc().isoformat()
            self.store.upsert_session(row)
            self.capture.register_watch(
                row["symbol"], signal.direction.value, float(levels.stop), float(levels.target),
                session.t120, quote.time,
            )
            self._event(row, "ENTRY_FILLED", quote.time, {
                "signal_id": signal.signal_id,
                "direction": signal.direction.value,
                "bid": _s(quote.bid),
                "ask": _s(quote.ask),
                "entry": _s(levels.entry),
                "stop": _s(levels.stop),
                "target": _s(levels.target),
                "quantity": _s(levels.quantity),
                "risk_cash": _s(levels.risk_cash),
                "rr_effective": _s(levels.rr_effective),
                "paper_equity": _s(profile.allocated_equity),
                "risk_fraction": _s(DEFAULT_ORB_CONFIG.risk_fraction),
                "cost_model": profile.cost_model,
                "data_resolution": profile.data_resolution,
                "quote_source": quote_raw.get("source"),
                "funding_estimate_per_unit": _s(funding_estimate),
            })
        except Exception as exc:
            self._mark_rejected(row, str(exc), _now_utc())

    def _scan_signal_boundary(self, boundary: datetime) -> None:
        sample_resolution = next(iter(self._eligible.values()))[1]
        sample_session = self._session_for(sample_resolution, boundary.date())
        sessions = {row["symbol"]: row for row in self.store.sessions_for_t0(sample_session.t0.isoformat())}
        targets = [
            symbol for symbol, row in sessions.items()
            if row["state"] == SessionState.WAIT_SIGNAL.value and not row["opportunity_consumed"]
        ]
        if not targets:
            return
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(self._fetch_candles_for_boundary, symbol, boundary, 2): symbol
                for symbol in targets
            }
            for future in as_completed(future_map):
                symbol = future_map[future]
                row = sessions[symbol]
                try:
                    last_eval = _parse_iso(row["last_evaluated_close"]) if row.get("last_evaluated_close") else None
                    if last_eval is not None and last_eval >= boundary:
                        continue
                    candles = future.result()
                    target_open = boundary - timedelta(minutes=5)
                    candle = next((c for c in candles if c.open_time == target_open), None)
                    if candle is None:
                        raise ValueError("DATA_ERROR: closed M5 candle missing")
                    resolution = self._eligible[symbol][1]
                    profile = resolution.profile
                    assert profile is not None
                    session = self._session_for(resolution, boundary.date())
                    opening = OpeningRange(
                        high=Decimal(str(row["range_high"])),
                        low=Decimal(str(row["range_low"])),
                        width=Decimal(str(row["range_high"])) - Decimal(str(row["range_low"])),
                        frozen_at=session.t0 + timedelta(minutes=15),
                    )
                    signal = evaluate_signal(candle, session, opening, profile)
                    row["last_evaluated_close"] = boundary.isoformat()
                    row["updated_at"] = _now_utc().isoformat()
                    self.store.upsert_session(row)
                    if signal is not None:
                        self._enter_paper(row, resolution, opening, signal, session)
                except Exception as exc:
                    row["data_quality_flags"] = json.dumps([str(exc)])
                    row["updated_at"] = _now_utc().isoformat()
                    self.store.upsert_session(row)

    def _close_no_signal_sessions(self, boundary: datetime) -> None:
        if not self._eligible:
            return
        sample_resolution = next(iter(self._eligible.values()))[1]
        session = self._session_for(sample_resolution, boundary.date())
        for row in self.store.sessions_for_t0(session.t0.isoformat()):
            if row["state"] != SessionState.WAIT_SIGNAL.value or row["opportunity_consumed"]:
                continue
            row["state"] = SessionState.SKIPPED.value
            row["rejection_reason"] = "NO_SIGNAL_BY_T60"
            row["last_evaluated_close"] = boundary.isoformat()
            row["updated_at"] = _now_utc().isoformat()
            self.store.upsert_session(row)
            self._event(row, "SESSION_NO_SIGNAL", boundary, {"reason": "NO_SIGNAL_BY_T60"}, notify=False)

    def _exit_fill(self, row: Dict[str, Any], quote: Dict[str, Any], reason: str, profile) -> None:
        qtime = _parse_iso(str(quote["time"]))
        bid = Decimal(str(quote["bid"]))
        ask = Decimal(str(quote["ask"]))
        direction = Direction(str(row["direction"]))
        entry = Decimal(str(row["entry_price"]))
        quantity = Decimal(str(row["quantity"]))
        stop = Decimal(str(row["stop_price"]))
        target = Decimal(str(row["target_price"]))
        delta = profile.tick_size

        if reason == "STOP":
            price = bid - Decimal(profile.slippage_stop_ticks) * delta if direction is Direction.LONG else ask + Decimal(profile.slippage_stop_ticks) * delta
            exit_fee_rate = profile.fee_rate_exit_stop
        elif reason == "TARGET":
            price = target
            exit_fee_rate = profile.fee_rate_exit_target
        else:
            price = bid - Decimal(profile.slippage_time_ticks) * delta if direction is Direction.LONG else ask + Decimal(profile.slippage_time_ticks) * delta
            exit_fee_rate = profile.fee_rate_exit_time

        gross = direction.sign * quantity * profile.point_value * (price - entry)
        entry_fee = quantity * profile.point_value * abs(entry) * profile.fee_rate_entry
        exit_fee = quantity * profile.point_value * abs(price) * exit_fee_rate
        funding_cash = self._realized_funding_cash(row, qtime, profile)
        costs = entry_fee + exit_fee + funding_cash
        net = gross - costs
        risk_cash = Decimal(str(row["risk_cash"]))
        r_multiple = net / risk_cash if risk_cash > 0 else Decimal("0")

        row["state"] = SessionState.DONE.value
        row["exit_time"] = qtime.isoformat()
        row["exit_price"] = _s(price)
        row["exit_reason"] = reason
        row["costs_cash"] = _s(costs)
        row["pnl_gross"] = _s(gross)
        row["pnl_net"] = _s(net)
        row["r_multiple"] = _s(r_multiple)
        row["updated_at"] = _now_utc().isoformat()
        self.store.upsert_session(row)
        self._event(row, "EXIT_FILLED", qtime, {
            "direction": direction.value,
            "exit_reason": reason,
            "exit_price": _s(price),
            "entry_price": _s(entry),
            "quantity": _s(quantity),
            "costs_cash": _s(costs),
            "funding_cash": _s(funding_cash),
            "entry_fee_cash": _s(entry_fee),
            "exit_fee_cash": _s(exit_fee),
            "pnl_gross": _s(gross),
            "pnl_net": _s(net),
            "r_multiple": _s(r_multiple),
            "risk_cash": _s(risk_cash),
        })

    def _monitor_open_positions(self, now: datetime) -> None:
        for row in self.store.open_sessions():
            symbol = str(row["symbol"]).upper()
            trigger = self.capture.pop_trigger(symbol)
            if trigger is None:
                continue
            reason = str(trigger.get("reason") or "")
            quote = dict(trigger.get("quote") or {})
            if reason == "DATA_GAP":
                row["state"] = SessionState.ERROR_RECONCILE.value
                row["rejection_reason"] = "MARKET_DATA_STREAM_GAP_DURING_OPEN_TRADE"
                row["updated_at"] = now.isoformat()
                self.store.upsert_session(row)
                self._event(row, "EXIT_UNRESOLVED", now, {
                    "exit_reason": "UNRESOLVED",
                    "reason": row["rejection_reason"],
                })
                continue
            resolution = self._eligible.get(symbol)
            if resolution is None or resolution[1].profile is None:
                row["state"] = SessionState.ERROR_RECONCILE.value
                row["rejection_reason"] = "PROFILE_MISSING_DURING_EXIT"
                row["updated_at"] = now.isoformat()
                self.store.upsert_session(row)
                continue
            try:
                self._exit_fill(row, quote, reason, resolution[1].profile)
            except Exception as exc:
                row["state"] = SessionState.ERROR_RECONCILE.value
                row["exit_time"] = quote.get("time")
                row["exit_reason"] = "UNRESOLVED"
                row["rejection_reason"] = f"EXIT_ACCOUNTING_UNRESOLVED:{type(exc).__name__}"
                row["updated_at"] = now.isoformat()
                self.store.upsert_session(row)
                self._event(row, "EXIT_UNRESOLVED", now, {
                    "exit_reason": "UNRESOLVED",
                    "reason": row["rejection_reason"],
                })

    def _reconcile_restart_gaps(self) -> None:
        now = _now_utc()
        for row in self.store.open_sessions():
            row["state"] = SessionState.ERROR_RECONCILE.value
            row["rejection_reason"] = "RUNTIME_RESTART_WITH_OPEN_PAPER_POSITION_DATA_GAP"
            row["updated_at"] = now.isoformat()
            self.store.upsert_session(row)
            self._event(row, "EXIT_UNRESOLVED", now, {
                "exit_reason": "UNRESOLVED",
                "reason": row["rejection_reason"],
            })

    @staticmethod
    def _latest_five_minute_boundary(now: datetime) -> datetime:
        floored = now.replace(second=0, microsecond=0)
        return floored - timedelta(minutes=floored.minute % 5)

    def run_cycle(self, now: Optional[datetime] = None) -> None:
        if self.adapter is None:
            raise RuntimeError("ORB scanner adapter not attached")
        now = (now or _now_utc()).astimezone(timezone.utc)
        self.total_cycles += 1
        self.last_cycle_at = now.isoformat()
        try:
            self._prepare_current_date(now)
            if self._eligible:
                sample_resolution = next(iter(self._eligible.values()))[1]
                session = self._session_for(sample_resolution, now.date())
                boundary = self._latest_five_minute_boundary(now)
                boundary_ready = now >= boundary + timedelta(seconds=1)
                if boundary_ready and boundary != self._last_boundary:
                    if boundary == session.t0 + timedelta(minutes=15):
                        self._build_ranges(boundary)
                        self.total_bar_batches += 1
                    elif session.t0 + timedelta(minutes=20) <= boundary < session.t60:
                        self._scan_signal_boundary(boundary)
                        self.total_bar_batches += 1
                    elif boundary == session.t60:
                        self._close_no_signal_sessions(boundary)
                    self._last_boundary = boundary
            self._monitor_open_positions(now)
        except Exception:
            self.total_errors += 1
            _logger.exception("ORB prospective cycle failed")

    def _loop(self, interval_seconds: float) -> None:
        next_refresh = 0.0
        while not self._stop.wait(interval_seconds):
            try:
                if time.monotonic() >= next_refresh:
                    self.refresh_universe()
                    next_refresh = time.monotonic() + 300.0
                self.run_cycle()
            except Exception:
                self.total_errors += 1
                _logger.exception("ORB prospective loop failure")

    def start(self, adapter: Any, interval_seconds: float = 1.0) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.adapter = adapter
        self.notifier.set_market_adapter(adapter)
        self.refresh_universe()
        self._reconcile_restart_gaps()
        self.capture.start()
        self._stop.clear()
        self.started_at = _now_utc()
        self._prepared_date = None
        self._last_boundary = None
        self._thread = threading.Thread(
            target=self._loop,
            args=(max(0.5, float(interval_seconds)),),
            daemon=True,
            name="HAGMARTK-ORB-Shadow",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        self._thread = None
        self.capture.stop()

    def status(self) -> Dict[str, Any]:
        now = _now_utc()
        today_t0 = None
        next_t0 = None
        state_counts: Dict[str, int] = {}
        if self._eligible:
            sample_resolution = next(iter(self._eligible.values()))[1]
            try:
                today = self._session_for(sample_resolution, now.date())
                today_t0 = today.t0
                state_counts = self.store.state_counts(today.t0.isoformat())
                if now < today.t0 + timedelta(minutes=15):
                    next_t0 = today.t0
                else:
                    tomorrow = self._session_for(sample_resolution, now.date() + timedelta(days=1))
                    next_t0 = tomorrow.t0
            except Exception:
                pass
        return {
            "strategy_id": DEFAULT_ORB_CONFIG.strategy_id,
            "version": DEFAULT_ORB_CONFIG.strategy_version,
            "stage": "SHADOW",
            "running": bool(self._thread and self._thread.is_alive()),
            "started_at": self.started_at.isoformat(),
            "last_cycle_at": self.last_cycle_at or None,
            "total_cycles": self.total_cycles,
            "total_errors": self.total_errors,
            "bar_batches": self.total_bar_batches,
            "catalog_total": self._catalog_total,
            "eligible_instruments": len(self._eligible),
            "unsupported_reasons": dict(self._reasons),
            "session_reference": "00:00 UTC explicit daily research reference",
            "today_t0": today_t0.isoformat() if today_t0 else None,
            "next_reference_t0": next_t0.isoformat() if next_t0 else None,
            "today_state_counts": state_counts,
            "open_positions": len(self.store.open_sessions()),
            "events_total": self.store.total_events(),
            "config_hash": ORB_V1_CONFIG_HASH,
            "paper_only": True,
            "real_order_execution_enabled": False,
            "execution_profile": "BINANCE_M5_LAST + first post-signal FSTREAM Bid/Ask + event-sequenced exits + explicit fee/funding/slippage model",
            "book_ticker_capture": self.capture.status(),
        }
