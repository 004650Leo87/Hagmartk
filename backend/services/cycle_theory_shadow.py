from __future__ import annotations

import hashlib
import itertools
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from backend.strategies.cycle_theory.broker import Candle, Deal, MockBroker, PendingOrder, Position
from backend.strategies.cycle_theory.enums import BotState, OrderType, PositionType
from backend.strategies.cycle_theory.historical_replay import ReplayBar, _atr
from backend.strategies.cycle_theory.inputs import baseline_inputs
from backend.strategies.cycle_theory.research_adapter import CycleTheoryResearchAdapter
from backend.strategies.cycle_theory.tick_execution import CycleTheoryTickExecutionHarness
from backend.strategies.cycle_theory.time_domain import CycleTheoryBrokerClock
from backend.strategies.cycle_theory.validation_candidate import (
    CYCLE_THEORY_V111_BASELINE,
    CYCLE_THEORY_V111_BASELINE_HASH,
)
from backend.services.cycle_theory_shadow_store import CycleTheoryShadowStore
from backend.services.telegram_notifier import TelegramNotifier

_logger = logging.getLogger(__name__)
_SAO_PAULO = ZoneInfo("America/Sao_Paulo")
_OPENING_POLICY_KEY = "__GLOBAL_WEEKLY_OPEN__"

_PUBLISH_TYPES = {
    "EXPANSION_WAIT_BUY", "EXPANSION_WAIT_SELL", "SETUP_REVERSED",
    "EXPANSION_CONFIRMED", "ORDER_SUBMITTED", "LIMIT_FILLED",
    "PARTIAL_EXECUTED", "BREAKEVEN_APPLIED", "TARGET_LEVEL_REACHED",
    "TAKE_PROFIT", "STOP_LOSS", "POSITION_CLOSED", "PULLBACK_MISSED",
}


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Expected timezone-aware market timestamp")
    return parsed.astimezone(timezone.utc)


def _week_key(local_dt: datetime) -> str:
    local_date = local_dt.date()
    if local_dt.weekday() == 6:  # domingo pertence ? semana que abre na segunda seguinte
        monday = local_date + timedelta(days=1)
    else:
        monday = local_date - timedelta(days=local_dt.weekday())
    return monday.isoformat()


def _is_24_7(symbol_row: dict[str, Any]) -> bool:
    path = str(symbol_row.get("broker_path") or symbol_row.get("path") or "").lower()
    return path.startswith("cryptos\\") or path.startswith("24-7\\")


def select_cycle_timeframe(symbol_row: dict[str, Any], local_dt: datetime, opening_trade_seen: bool) -> str:
    """User-approved operating policy: Sunday weekly opening uses M15 first; weekdays use M5.

    24/7 instruments have no weekly reopen, so they remain M5. For weekend-closed
    instruments M15 remains active on Sunday until the first paper order is generated.
    """
    if not _is_24_7(symbol_row) and local_dt.weekday() == 6 and not opening_trade_seen:
        return "M15"
    return "M5"


@dataclass
class CycleRuntimeContext:
    symbol: str
    market: str
    symbol_row: dict[str, Any]
    timeframe: str
    broker: MockBroker
    strategy: CycleTheoryResearchAdapter
    execution: CycleTheoryTickExecutionHarness
    telemetry_cursor: int = 0
    last_tick_utc: datetime | None = None
    last_bucket_utc: datetime | None = None
    last_bar_refresh_monotonic: float = 0.0
    last_checkpoint_signature: str = ""
    last_checkpoint_monotonic: float = 0.0
    errors: int = 0

    def has_active_trade(self) -> bool:
        return self.broker.has_active_trade(self.strategy.inputs.magic_num, self.symbol)


class CycleTheoryProspectiveScanner:
    """Read-only market observer + PAPER lifecycle for frozen Cycle Theory V111."""

    def __init__(
        self,
        store: CycleTheoryShadowStore | None = None,
        notifier: TelegramNotifier | None = None,
    ) -> None:
        self.store = store or CycleTheoryShadowStore()
        self.notifier = notifier or TelegramNotifier()
        self.contexts: dict[str, CycleRuntimeContext] = {}
        self.symbol_rows: dict[str, dict[str, Any]] = {}
        self.clock: CycleTheoryBrokerClock | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.last_cycle_at = ""
        self.total_cycles = 0
        self.total_errors = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _new_broker(self, row: dict[str, Any]) -> MockBroker:
        return MockBroker(
            symbol=str(row["symbol"]),
            point=float(row.get("point") or 0.00001),
            digits=int(row.get("digits") or 5),
            stops_level_pts=int(row.get("trade_stops_level") or 0),
            freeze_level_pts=int(row.get("trade_freeze_level") or 0),
            volume_step=float(row.get("volume_step") or 0.01),
            volume_min=float(row.get("volume_min") or 0.01),
            volume_max=float(row.get("volume_max") or 100.0),
        )

    def _new_context(self, row: dict[str, Any], timeframe: str) -> CycleRuntimeContext:
        broker = self._new_broker(row)
        inputs = baseline_inputs()
        strategy = CycleTheoryResearchAdapter(
            symbol=str(row["symbol"]), inputs=inputs, broker=broker, timeframe=timeframe,
            terms_accepted=True,
        )
        execution = CycleTheoryTickExecutionHarness(broker)
        strategy.power_on()
        context = CycleRuntimeContext(
            symbol=str(row["symbol"]),
            market=str(row.get("category") or "OTHER"),
            symbol_row=dict(row), timeframe=timeframe, broker=broker,
            strategy=strategy, execution=execution,
            telemetry_cursor=len(strategy.sm.telemetry.events),
        )
        self._restore_runtime(context)
        return context

    def refresh_universe(self, adapter: Any) -> int:
        rows = adapter.get_symbols()
        self.symbol_rows = {
            str(row.get("symbol") or "").upper(): dict(row)
            for row in rows if str(row.get("symbol") or "").strip()
        }
        return len(self.symbol_rows)

    def _desired_timeframe(self, context: CycleRuntimeContext, tick_utc: datetime) -> str:
        local_dt = tick_utc.astimezone(_SAO_PAULO)
        week = _week_key(local_dt)
        seen = self.store.get_policy(_OPENING_POLICY_KEY, week)
        return select_cycle_timeframe(context.symbol_row, local_dt, seen)

    @staticmethod
    def _bucket_start(tick_utc: datetime, timeframe: str) -> datetime:
        minutes = 15 if timeframe == "M15" else 5
        minute = (tick_utc.minute // minutes) * minutes
        return tick_utc.replace(minute=minute, second=0, microsecond=0)

    def _refresh_bars(self, adapter: Any, context: CycleRuntimeContext) -> None:
        assert self.clock is not None
        rows = adapter.get_candles(context.symbol, context.timeframe, count=40)
        replay_rows: list[ReplayBar] = []
        candles: list[Candle] = []
        for row in rows:
            server_time = self.clock.iso_utc_to_server_naive(str(row["time"]))
            replay_rows.append(ReplayBar(
                time=server_time, open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                spread_points=int(row.get("spread") or 0),
            ))
        replay_rows.sort(key=lambda bar: bar.time)
        for bar in reversed(replay_rows):
            candles.append(Candle(bar.time, bar.open, bar.high, bar.low, bar.close))
        context.broker.set_bars(context.timeframe, candles)
        context.broker.atr_value = _atr(replay_rows, context.strategy.inputs.atr_period)
        context.last_bar_refresh_monotonic = time.monotonic()

    def _levels(self, context: CycleRuntimeContext) -> dict[str, float]:
        s = context.strategy.sm.state
        direction = s.setup_dir
        entry = 0.0
        stop = 0.0
        if context.broker.pending_orders:
            order = context.broker.pending_orders[0]
            entry, stop = order.price_open, order.sl
            direction = 1 if order.type is OrderType.BUY_LIMIT else -1
        elif context.broker.positions:
            pos = context.broker.positions[0]
            entry, stop = pos.price_open, pos.sl
            direction = 1 if pos.type is PositionType.BUY else -1
        elif s.exp_level and s.super_size:
            pb = s.super_size * 0.25
            if direction == 1:
                entry, stop = s.exp_level - pb, s.g_sl_ref - (context.strategy.inputs.stop_buffer * context.broker.point)
            elif direction == -1:
                entry, stop = s.exp_level + pb, s.g_sl_ref + (context.strategy.inputs.stop_buffer * context.broker.point)
        targets = [0.0, 0.0, 0.0]
        if entry and s.super_size and direction:
            sign = 1 if direction == 1 else -1
            targets = [entry + sign * s.super_size * i for i in (1, 2, 3)]
        return {
            "channel_high": s.ch_high, "channel_low": s.ch_low, "expansion": s.exp_level,
            "entry": entry, "stop": stop,
            "target_1": targets[0], "target_2": targets[1], "target_3": targets[2],
        }

    def _direction(self, context: CycleRuntimeContext, payload: dict[str, Any]) -> str:
        if "is_buy" in payload:
            return "BUY" if payload["is_buy"] else "SELL"
        raw = payload.get("dir", payload.get("to", context.strategy.sm.state.setup_dir))
        try:
            direction = int(raw)
        except (TypeError, ValueError):
            direction = 0
        return "BUY" if direction > 0 else "SELL" if direction < 0 else "NEUTRO"

    def _record_event(
        self, context: CycleRuntimeContext, event_type: str,
        payload: dict[str, Any], event_time: datetime,
    ) -> bool:
        direction = self._direction(context, payload)
        levels = self._levels(context)
        clean_payload = dict(payload)
        clean_payload.setdefault("detail", self._human_detail(event_type, payload))
        identity = json.dumps({
            "candidate": CYCLE_THEORY_V111_BASELINE.candidate_id,
            "symbol": context.symbol, "timeframe": context.timeframe,
            "event_type": event_type, "event_time": event_time.isoformat(),
            "payload": clean_payload,
        }, sort_keys=True, default=str)
        event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        event = {
            "event_id": event_id,
            "candidate_id": CYCLE_THEORY_V111_BASELINE.candidate_id,
            "parameter_hash": CYCLE_THEORY_V111_BASELINE_HASH,
            "symbol": context.symbol, "market": context.market,
            "timeframe": context.timeframe, "event_type": event_type,
            "direction": direction, "event_time": event_time.isoformat(),
            "payload": clean_payload, "levels": levels,
        }
        inserted = self.store.add_event(event)
        if inserted and event_type in _PUBLISH_TYPES:
            self.notifier.notify_cycle_async(event)
        if inserted and event_type == "ORDER_SUBMITTED" and context.timeframe == "M15":
            local_dt = event_time.astimezone(timezone.utc).astimezone(_SAO_PAULO)
            self.store.set_opening_trade_seen(_OPENING_POLICY_KEY, _week_key(local_dt), True)
        return inserted

    @staticmethod
    def _human_detail(event_type: str, payload: dict[str, Any]) -> str:
        mapping = {
            "EXPANSION_WAIT_BUY": "O fechamento confirmou rompimento inicial acima do canal; o motor aguarda a expans?o de compra.",
            "EXPANSION_WAIT_SELL": "O fechamento confirmou rompimento inicial abaixo do canal; o motor aguarda a expans?o de venda.",
            "SETUP_REVERSED": "A estrutura rompeu o lado oposto e o motor inverteu a dire??o do ciclo.",
            "EXPANSION_CONFIRMED": "A segunda etapa da expans?o foi confirmada pelas regras originais V111.",
            "ORDER_SUBMITTED": "O motor gerou uma ordem virtual de pullback. Nenhuma ordem foi enviada ? corretora.",
            "LIMIT_FILLED": "O pre?o real Bid/Ask alcan?ou a entrada virtual e ativou a posi??o PAPER.",
            "PULLBACK_MISSED": "O pre?o atingiu o primeiro objetivo antes do pullback; a entrada virtual foi cancelada.",
            "PARTIAL_EXECUTED": "Uma parcial prevista pela V111 foi executada somente no livro PAPER.",
            "BREAKEVEN_APPLIED": "A prote??o de breakeven da V111 foi aplicada somente ? posi??o virtual.",
            "TARGET_LEVEL_REACHED": "O pre?o alcan?ou um n?vel de expans?o acompanhado pelo motor.",
            "TAKE_PROFIT": "O pre?o Bid/Ask observado alcan?ou o alvo final da posi??o virtual.",
            "STOP_LOSS": "O pre?o Bid/Ask observado alcan?ou o stop da posi??o virtual.",
            "POSITION_CLOSED": "A posi??o virtual foi encerrada pelas regras originais do ciclo.",
        }
        return mapping.get(event_type, str(payload.get("reason") or event_type.replace("_", " ")))

    def _drain_telemetry(self, context: CycleRuntimeContext, event_time: datetime) -> int:
        events = context.strategy.sm.telemetry.events
        new = events[context.telemetry_cursor:]
        for item in new:
            self._record_event(context, item.type.name, dict(item.payload), event_time)
        context.telemetry_cursor = len(events)
        return len(new)

    def _process_tick(self, context: CycleRuntimeContext, bid: float, ask: float, tick_utc: datetime) -> None:
        assert self.clock is not None
        server_time = self.clock.utc_to_server_naive(tick_utc)
        execution_events = context.execution.process_tick(bid=bid, ask=ask, at=server_time)
        for item in execution_events:
            self._record_event(context, item.kind, {
                "ticket": item.ticket, "price": item.price,
                "points": item.points, "r_multiple": item.r_multiple,
            }, tick_utc)
        context.strategy.on_tick()
        self._drain_telemetry(context, tick_utc)
        context.last_tick_utc = tick_utc

    def _process_market_delta(self, adapter: Any, context: CycleRuntimeContext, quote: dict[str, Any]) -> None:
        tick_utc = _parse_utc(str(quote["time"]))
        bid, ask = float(quote["bid"]), float(quote["ask"])
        if bid <= 0 or ask <= 0 or ask < bid:
            return
        desired = self._desired_timeframe(context, tick_utc)
        if desired != context.timeframe and not context.has_active_trade():
            context = self._new_context(context.symbol_row, desired)
            self.contexts[context.symbol] = context
        bucket = self._bucket_start(tick_utc, context.timeframe)
        refresh_due = (
            context.last_bucket_utc != bucket
            or not context.broker.bars.get(context.timeframe)
            or (context.has_active_trade() and time.monotonic() - context.last_bar_refresh_monotonic >= 30.0)
        )
        if refresh_due:
            self._refresh_bars(adapter, context)
            context.last_bucket_utc = bucket
        if context.has_active_trade() and context.last_tick_utc and tick_utc > context.last_tick_utc:
            start = context.last_tick_utc + timedelta(milliseconds=1)
            if tick_utc - start <= timedelta(hours=2):
                ticks = adapter.get_ticks(context.symbol, start, tick_utc)
                for row in ticks:
                    observed_utc = _parse_utc(str(row["time"]))
                    if context.last_tick_utc and observed_utc <= context.last_tick_utc:
                        continue
                    self._process_tick(context, float(row["bid"]), float(row["ask"]), observed_utc)
                if context.last_tick_utc and context.last_tick_utc >= tick_utc:
                    self._save_runtime(context)
                    return
        self._process_tick(context, bid, ask, tick_utc)
        self._save_runtime(context)

    def scan_once(self, adapter: Any) -> dict[str, Any]:
        if self.clock is None:
            self.clock = CycleTheoryBrokerClock.from_runtime_scope(adapter.get_runtime_scope())
        if not self.symbol_rows:
            self.refresh_universe(adapter)
        processed = 0
        errors = 0
        for symbol, row in list(self.symbol_rows.items()):
            try:
                quote = adapter.get_quote(symbol)
                tick_utc = _parse_utc(str(quote["time"]))
                if symbol not in self.contexts:
                    local_dt = tick_utc.astimezone(_SAO_PAULO)
                    seen = self.store.get_policy(_OPENING_POLICY_KEY, _week_key(local_dt))
                    tf = select_cycle_timeframe(row, local_dt, seen)
                    saved = self.store.load_runtime(symbol)
                    if saved and (saved.get("positions") or saved.get("pending_orders")):
                        saved_tf = str(saved.get("timeframe") or "").upper()
                        if saved_tf in {"M5", "M15"}:
                            tf = saved_tf
                    self.contexts[symbol] = self._new_context(row, tf)
                self._process_market_delta(adapter, self.contexts[symbol], quote)
                processed += 1
            except Exception as exc:
                errors += 1
                self.total_errors += 1
                if symbol in self.contexts:
                    self.contexts[symbol].errors += 1
                _logger.debug("[CYCLE_SHADOW] %s unavailable/error: %s", symbol, type(exc).__name__)
        self.total_cycles += 1
        self.last_cycle_at = datetime.now(timezone.utc).isoformat()
        return {"processed_symbols": processed, "errors": errors, "universe": len(self.symbol_rows)}

    def start(self, adapter: Any, interval_seconds: float = 3.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def worker() -> None:
            next_universe_refresh = 0.0
            while not self._stop.is_set():
                try:
                    if time.monotonic() >= next_universe_refresh:
                        self.refresh_universe(adapter)
                        next_universe_refresh = time.monotonic() + 3600.0
                    self.scan_once(adapter)
                except Exception:
                    self.total_errors += 1
                    _logger.exception("[CYCLE_SHADOW] scanner cycle failed")
                self._stop.wait(interval_seconds)

        self._thread = threading.Thread(target=worker, daemon=True, name="CycleTheoryShadow")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def status(self) -> dict[str, Any]:
        active = sum(1 for ctx in self.contexts.values() if ctx.has_active_trade())
        by_tf = {"M5": 0, "M15": 0}
        for ctx in self.contexts.values():
            by_tf[ctx.timeframe] = by_tf.get(ctx.timeframe, 0) + 1
        return {
            "enabled": bool(self._thread and self._thread.is_alive()),
            "candidate_id": CYCLE_THEORY_V111_BASELINE.candidate_id,
            "parameter_hash": CYCLE_THEORY_V111_BASELINE_HASH,
            "universe_symbols": len(self.symbol_rows),
            "contexts": len(self.contexts), "active_paper_trades": active,
            "timeframes": by_tf, "cycles": self.total_cycles,
            "errors": self.total_errors, "last_cycle_at": self.last_cycle_at,
            "real_order_execution_enabled": False,
            "telegram": self.notifier.status(),
            "ledger": self.store.summary(),
        }

    def _save_runtime(self, context: CycleRuntimeContext) -> None:
        s = context.strategy.sm.state
        def dt(value: datetime | None) -> str | None:
            return value.isoformat() if value else None
        snapshot = {
            "timeframe": context.timeframe,
            "state": {
                **{k: v for k, v in asdict(s).items() if k not in {"current_state", "last_order_time", "ref_time_start"}},
                "current_state": s.current_state.name,
                "last_order_time": dt(s.last_order_time), "ref_time_start": dt(s.ref_time_start),
            },
            "positions": [
                {**asdict(p), "type": p.type.name} for p in context.broker.positions
            ],
            "pending_orders": [
                {**asdict(o), "type": o.type.name} for o in context.broker.pending_orders
            ],
            "last_tick_utc": dt(context.last_tick_utc),
            "initial_risk": {str(k): v for k, v in context.execution._initial_risk_by_ticket.items()},
        }
        signature_payload = dict(snapshot)
        signature_payload.pop("last_tick_utc", None)
        signature = hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        elapsed = time.monotonic() - context.last_checkpoint_monotonic
        min_interval = 5.0 if context.has_active_trade() else 60.0
        if signature == context.last_checkpoint_signature and elapsed < min_interval:
            return
        self.store.save_runtime(context.symbol, snapshot)
        context.last_checkpoint_signature = signature
        context.last_checkpoint_monotonic = time.monotonic()

    def _restore_runtime(self, context: CycleRuntimeContext) -> None:
        snapshot = self.store.load_runtime(context.symbol)
        if not snapshot or snapshot.get("timeframe") != context.timeframe:
            return
        state = snapshot.get("state") or {}
        s = context.strategy.sm.state
        for key, value in state.items():
            if key == "current_state":
                s.current_state = BotState[value]
            elif key in {"last_order_time", "ref_time_start"}:
                setattr(s, key, datetime.fromisoformat(value) if value else None)
            elif hasattr(s, key):
                setattr(s, key, value)
        context.broker.positions = [
            Position(**{**row, "type": PositionType[row["type"]]})
            for row in snapshot.get("positions", [])
        ]
        context.broker.pending_orders = [
            PendingOrder(**{**row, "type": OrderType[row["type"]]})
            for row in snapshot.get("pending_orders", [])
        ]
        tickets = [p.ticket for p in context.broker.positions] + [o.ticket for o in context.broker.pending_orders]
        context.broker._ticket_seq = itertools.count(max(tickets, default=0) + 1)
        raw_last = snapshot.get("last_tick_utc")
        context.last_tick_utc = datetime.fromisoformat(raw_last) if raw_last else None
        context.execution._initial_risk_by_ticket = {
            int(k): v for k, v in (snapshot.get("initial_risk") or {}).items()
        }
