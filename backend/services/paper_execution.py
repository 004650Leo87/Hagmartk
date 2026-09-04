from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.core.time_utils import now_utc_str, parse_utc_timestamp
from backend.domain.shadow_models import ShadowEvent, ShadowEventType, ShadowState
from backend.services.alert_engine import InternalShadowPublisher
from backend.services.shadow_store import ShadowStoreRepository


class ShadowPaperExecutionEngine:
    """Executa virtualmente eventos Shadow usando candles reais fechados.

    Nunca envia ordens ao broker. O estado persistido simula o lifecycle operacional
    que futuramente poderá alimentar um executor real, após aprovação explícita.
    """

    def __init__(
        self,
        store: ShadowStoreRepository,
        publisher: Optional[InternalShadowPublisher] = None,
        max_activation_bars: int = 5,
    ) -> None:
        self.store = store
        self.publisher = publisher or InternalShadowPublisher(store)
        self.max_activation_bars = int(max_activation_bars)

    @staticmethod
    def _excluded(evt: ShadowEvent) -> bool:
        meta = evt.metadata or {}
        return evt.event_id.startswith("test_") or bool(meta.get("is_test") or meta.get("synthetic"))
    @staticmethod
    def _candle_values(candle: Dict[str, Any]) -> tuple[str, float, float, float, float]:
        candle_time = str(candle.get("time") or "")
        return (
            candle_time,
            float(candle.get("open", 0.0)),
            float(candle.get("high", 0.0)),
            float(candle.get("low", 0.0)),
            float(candle.get("close", 0.0)),
        )

    def process_closed_candle(
        self, symbol: str, timeframe: str, candle: Dict[str, Any]
    ) -> List[ShadowEvent]:
        return self.process_candles(symbol, timeframe, [candle])

    def process_candles(
        self, symbol: str, timeframe: str, candles: List[Dict[str, Any]]
    ) -> List[ShadowEvent]:
        updated: List[ShadowEvent] = []
        ordered = sorted(candles, key=lambda row: str(row.get("time") or ""))
        for evt in self.store.list_active_events():
            if evt.symbol != symbol or evt.timeframe != timeframe or self._excluded(evt):
                continue
            cursor = parse_utc_timestamp(
                evt.market_candle_time or evt.activated_at or evt.armed_at or evt.confluence_time
            )
            touched = False
            for candle in ordered:
                candle_dt = parse_utc_timestamp(str(candle.get("time") or ""))
                if candle_dt is None or (cursor is not None and candle_dt <= cursor):
                    continue
                if evt.current_state == ShadowState.ARMED.value:
                    changed = self._advance_armed(evt, candle)
                elif evt.current_state == ShadowState.ACTIVATED.value:
                    changed = self._advance_activated(evt, candle)
                else:
                    break
                if changed is not None:
                    touched = True
                    cursor = candle_dt
            if touched:
                updated.append(evt)
        return updated
    def _publish(
        self,
        event_type: ShadowEventType,
        evt: ShadowEvent,
        from_state: str,
        candle_time: str,
        market_price: float,
        reason: str,
    ) -> None:
        self.publisher.publish(
            event_type,
            evt,
            {
                "from_state": from_state,
                "candle_timestamp": candle_time,
                "market_price": market_price,
                "reason": reason,
            },
        )

    @staticmethod
    def _direction(evt: ShadowEvent) -> str:
        return str(evt.direction or "").upper()

    def _persist(self, evt: ShadowEvent, candle_time: str) -> None:
        now = now_utc_str()
        evt.market_candle_time = candle_time
        evt.processed_at = now
        evt.updated_at = now
        self.store.update_event(evt)
    def _advance_armed(self, evt: ShadowEvent, candle: Dict[str, Any]) -> Optional[ShadowEvent]:
        candle_time, open_p, high_p, low_p, _ = self._candle_values(candle)
        candle_dt = parse_utc_timestamp(candle_time)
        armed_dt = parse_utc_timestamp(evt.armed_at or evt.confluence_time)
        if candle_dt is None or armed_dt is None or candle_dt <= armed_dt:
            return None

        meta = dict(evt.metadata or {})
        elapsed = int(meta.get("paper_activation_bars_elapsed", 0)) + 1
        meta["paper_activation_bars_elapsed"] = elapsed
        meta["execution_mode"] = "SHADOW_PAPER"
        evt.metadata = meta

        direction = self._direction(evt)
        if direction == "BULLISH":
            invalidated = low_p < evt.initial_stop
            activated = high_p >= evt.activation_level
        else:
            invalidated = high_p > evt.initial_stop
            activated = low_p <= evt.activation_level

        if invalidated:
            previous = evt.current_state
            evt.current_state = ShadowState.INVALIDATED.value
            meta["terminal_reason"] = "INVALIDATED_BEFORE_ACTIVATION"
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.SETUP_INVALIDATED, evt, previous, candle_time, evt.initial_stop, meta["terminal_reason"])
            return evt
        if activated:
            previous = evt.current_state
            if direction == "BULLISH":
                entry = max(open_p, evt.activation_level)
                risk = entry - evt.initial_stop
                target = entry + (2.0 * risk)
            else:
                entry = min(open_p, evt.activation_level)
                risk = evt.initial_stop - entry
                target = entry - (2.0 * risk)

            if risk <= 0.0:
                evt.current_state = ShadowState.INVALIDATED.value
                meta["terminal_reason"] = "INVALID_RISK_GEOMETRY"
                self._persist(evt, candle_time)
                self._publish(ShadowEventType.SETUP_INVALIDATED, evt, previous, candle_time, entry, meta["terminal_reason"])
                return evt

            evt.current_state = ShadowState.ACTIVATED.value
            evt.activated_at = candle_time
            evt.entry_price = float(entry)
            evt.initial_risk = float(risk)
            evt.target_2R = float(target)
            evt.bars_since_activation = 0
            meta["paper_entry_candle"] = candle_time
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.ENTRY_ACTIVATED, evt, previous, candle_time, entry, "PAPER_ENTRY_TRIGGERED")
            return self._evaluate_active_bar(evt, candle, increment_bar=False)

        if elapsed >= self.max_activation_bars:
            previous = evt.current_state
            evt.current_state = ShadowState.EXPIRED.value
            meta["terminal_reason"] = "MAX_ACTIVATION_BARS_EXCEEDED"
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.SETUP_EXPIRED, evt, previous, candle_time, float(candle.get("close", 0.0)), meta["terminal_reason"])
            return evt

        self._persist(evt, candle_time)
        return evt
    def _advance_activated(self, evt: ShadowEvent, candle: Dict[str, Any]) -> Optional[ShadowEvent]:
        candle_time, _, _, _, _ = self._candle_values(candle)
        candle_dt = parse_utc_timestamp(candle_time)
        activated_dt = parse_utc_timestamp(evt.activated_at)
        if candle_dt is None or activated_dt is None or candle_dt <= activated_dt:
            return None
        return self._evaluate_active_bar(evt, candle, increment_bar=True)

    def _evaluate_active_bar(
        self,
        evt: ShadowEvent,
        candle: Dict[str, Any],
        *,
        increment_bar: bool,
    ) -> ShadowEvent:
        candle_time, _, high_p, low_p, _ = self._candle_values(candle)
        risk = float(evt.initial_risk or 0.0)
        if risk <= 0.0:
            previous = evt.current_state
            evt.current_state = ShadowState.INVALIDATED.value
            evt.metadata = dict(evt.metadata or {})
            evt.metadata["terminal_reason"] = "INVALID_RISK_GEOMETRY"
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.SETUP_INVALIDATED, evt, previous, candle_time, evt.entry_price, "INVALID_RISK_GEOMETRY")
            return evt

        if increment_bar:
            evt.bars_since_activation = int(evt.bars_since_activation or 0) + 1

        direction = self._direction(evt)
        if direction == "BULLISH":
            favorable_r = max(0.0, (high_p - evt.entry_price) / risk)
            adverse_r = max(0.0, (evt.entry_price - low_p) / risk)
            target_hit = high_p >= evt.target_2R
            stop_hit = low_p <= evt.initial_stop
        else:
            favorable_r = max(0.0, (evt.entry_price - low_p) / risk)
            adverse_r = max(0.0, (high_p - evt.entry_price) / risk)
            target_hit = low_p <= evt.target_2R
            stop_hit = high_p >= evt.initial_stop
        evt.mfe_r_live = max(float(evt.mfe_r_live or 0.0), float(favorable_r))
        evt.mae_r_live = max(float(evt.mae_r_live or 0.0), float(adverse_r))
        meta = dict(evt.metadata or {})
        meta["execution_mode"] = "SHADOW_PAPER"
        evt.metadata = meta

        milestone_new = favorable_r >= 1.0 and not evt.milestone_1r_reached
        if milestone_new:
            evt.milestone_1r_reached = True
            self._persist(evt, candle_time)
            milestone_price = evt.entry_price + risk if direction == "BULLISH" else evt.entry_price - risk
            self._publish(
                ShadowEventType.MILESTONE_1R,
                evt,
                ShadowState.ACTIVATED.value,
                candle_time,
                milestone_price,
                "PAPER_MILESTONE_1R",
            )

        if target_hit and stop_hit:
            previous = evt.current_state
            evt.current_state = ShadowState.STOPPED.value
            meta["same_bar_ambiguous"] = True
            meta["terminal_reason"] = "TARGET_AND_STOP_SAME_BAR_STOP_FIRST"
            meta["realized_r_gross"] = -1.0
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.STOP_REACHED, evt, previous, candle_time, evt.initial_stop, meta["terminal_reason"])
            return evt

        if stop_hit:
            previous = evt.current_state
            evt.current_state = ShadowState.STOPPED.value
            meta["terminal_reason"] = "STRUCTURAL_STOP_REACHED"
            meta["realized_r_gross"] = -1.0
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.STOP_REACHED, evt, previous, candle_time, evt.initial_stop, meta["terminal_reason"])
            return evt
        if target_hit:
            previous = evt.current_state
            evt.current_state = ShadowState.TARGET_2R.value
            meta["terminal_reason"] = "TARGET_2R_REACHED"
            meta["realized_r_gross"] = 2.0
            self._persist(evt, candle_time)
            self._publish(ShadowEventType.TARGET_REACHED, evt, previous, candle_time, evt.target_2R, meta["terminal_reason"])
            return evt

        self._persist(evt, candle_time)
        return evt
