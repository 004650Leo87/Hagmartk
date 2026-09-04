from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from backend.core.time_utils import now_utc_str, parse_utc_timestamp
from backend.services.shadow_store import ShadowStoreRepository
from backend.strategies.hdf.fibonacci_audit import SOURCE_LEVELS, mirrored_extension_levels
from backend.strategies.hdf.prospective_fibonacci import (
    ConfirmedPivot,
    audit_strict_pre_reversal_leg,
)

PRE_MODE = "PRE_REVERSAL_STRICT_V1"
POST_MODE = "POST_REVERSAL_PATTERN_RANGE_V1"
RESEARCH_SCOPE = "HDF_FIBONACCI_RESEARCH_V1"


def _telemetry_id(symbol: str, timeframe: str, direction: str, decision_time: str, mode: str, source: str) -> str:
    raw = "|".join([symbol, timeframe, direction, decision_time, mode, source])
    return "fibtele_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _target_terminal(
    df: pd.DataFrame,
    entry_index: int,
    direction: str,
    target: float,
    stop: float,
) -> Dict[str, Any]:
    for k in range(entry_index, len(df)):
        high = float(df.iloc[k].high)
        low = float(df.iloc[k].low)
        target_hit = high >= target if direction == "BULLISH" else low <= target
        stop_hit = low <= stop if direction == "BULLISH" else high >= stop
        if target_hit and stop_hit:
            return {"state": "AMBIGUOUS_SAME_BAR", "bars": k - entry_index}
        if stop_hit:
            return {"state": "STOP_FIRST", "bars": k - entry_index}
        if target_hit:
            return {"state": "TARGET_FIRST", "bars": k - entry_index}
    return {"state": "PENDING", "bars": None}


def _target_outcomes(
    df: pd.DataFrame,
    entry_index: Optional[int],
    direction: str,
    entry_price: float,
    stop: float,
    levels: Dict[float, float],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for level, target in levels.items():
        level_key = str(float(level))
        ahead = target > entry_price if direction == "BULLISH" else target < entry_price
        if not ahead:
            out[level_key] = {"state": "BEHIND_ENTRY", "bars": None, "price": float(target)}
            continue
        if entry_index is None:
            out[level_key] = {"state": "NOT_ACTIVATED", "bars": None, "price": float(target)}
            continue
        terminal = _target_terminal(df, entry_index, direction, float(target), stop)
        out[level_key] = {
            "state": terminal["state"],
            "bars": terminal["bars"],
            "price": float(target),
        }
    return out


class FibonacciProspectiveTelemetryEngine:
    """Prospective research telemetry. Never promotes or executes a candidate."""

    def __init__(
        self,
        store: Optional[ShadowStoreRepository] = None,
        started_at: Optional[str] = None,
    ) -> None:
        self.store = store or ShadowStoreRepository()
        if started_at:
            self.started_at = started_at
        else:
            session = self.store.get_shadow_session(RESEARCH_SCOPE)
            if session and session.get("started_at"):
                self.started_at = str(session["started_at"])
            else:
                self.started_at = now_utc_str()
                self.store.save_shadow_session(RESEARCH_SCOPE, self.started_at, True)

    @staticmethod
    def _confirmed_pivots(strategy: Any, df: pd.DataFrame) -> List[ConfirmedPivot]:
        highs, lows = strategy.pivot_detector.find_pivots(df)
        return sorted(
            [ConfirmedPivot(p.index, p.price, p.is_high, p.confirmed_at_index, p.time) for p in highs + lows],
            key=lambda p: p.index,
        )

    def _effective_started_at(self, shadow_started_at: str) -> str:
        shadow_dt = parse_utc_timestamp(shadow_started_at)
        feature_dt = parse_utc_timestamp(self.started_at)
        if shadow_dt is None:
            return self.started_at
        if feature_dt is None:
            return shadow_started_at
        return self.started_at if feature_dt >= shadow_dt else shadow_started_at

    @staticmethod
    def _is_prospective(decision_time: str, shadow_started_at: str, is_synthetic: bool) -> bool:
        if is_synthetic:
            return True
        decision_dt = parse_utc_timestamp(decision_time)
        shadow_dt = parse_utc_timestamp(shadow_started_at)
        if decision_dt is None or shadow_dt is None:
            return False
        return decision_dt >= shadow_dt

    def process_occurrences(
        self,
        *,
        symbol: str,
        timeframe: str,
        df_closed: pd.DataFrame,
        occurrences: Iterable[Any],
        strategy: Any,
        shadow_started_at: str,
        candidate_id: str,
        is_synthetic: bool = False,
    ) -> int:
        if df_closed is None or df_closed.empty:
            return 0
        pivots = self._confirmed_pivots(strategy, df_closed)
        time_to_index = {str(value): i for i, value in enumerate(df_closed.time)}
        source = "TEST" if is_synthetic else "LIVE_PROSPECTIVE"
        written = 0

        for occ in occurrences:
            decision_time = str(occ.temporal_model.confluence_completed_at or "")
            effective_started_at = self._effective_started_at(shadow_started_at)
            if not decision_time or not self._is_prospective(decision_time, effective_started_at, is_synthetic):
                continue
            decision_index = time_to_index.get(decision_time)
            p2_index = time_to_index.get(str(occ.temporal_model.pivot_2_time))
            if decision_index is None or p2_index is None:
                continue

            pre = audit_strict_pre_reversal_leg(
                direction=occ.direction,
                pivots=pivots,
                decision_index=decision_index,
                reversal_pivot_index=p2_index,
                candle_low=float(df_closed.iloc[decision_index].low),
                candle_high=float(df_closed.iloc[decision_index].high),
            )
            pre_levels = (
                mirrored_extension_levels(pre.anchor_a.price, pre.anchor_b.price)
                if pre.anchor_a is not None and pre.anchor_b is not None
                else {}
            )
            pre_record = self._base_record(
                candidate_id=candidate_id,
                symbol=symbol,
                timeframe=timeframe,
                occ=occ,
                mode=PRE_MODE,
                role="CONFLUENCE",
                policy_id="STRICT_PRE_REVERSAL_LATEST_CONFIRMED_LEG_V1",
                decision_time=decision_time,
                source=source,
                is_synthetic=is_synthetic,
            )
            self._attach_pre_snapshot(pre_record, pre, pre_levels, df_closed)
            self.store.upsert_fibonacci_telemetry(pre_record)
            written += 1
            post_record = self._base_record(
                candidate_id=candidate_id,
                symbol=symbol,
                timeframe=timeframe,
                occ=occ,
                mode=POST_MODE,
                role="TARGET",
                policy_id="POST_REVERSAL_PATTERN_RANGE_V1",
                decision_time=decision_time,
                source=source,
                is_synthetic=is_synthetic,
            )
            self._attach_post_snapshot_and_outcomes(
                post_record,
                occ=occ,
                df_closed=df_closed,
                time_to_index=time_to_index,
            )
            self.store.upsert_fibonacci_telemetry(post_record)
            written += 1

        return written

    @staticmethod
    def _base_record(
        *,
        candidate_id: str,
        symbol: str,
        timeframe: str,
        occ: Any,
        mode: str,
        role: str,
        policy_id: str,
        decision_time: str,
        source: str,
        is_synthetic: bool,
    ) -> Dict[str, Any]:
        now = now_utc_str()
        return {
            "telemetry_id": _telemetry_id(symbol, timeframe, occ.direction, decision_time, mode, source),
            "research_scope": RESEARCH_SCOPE,
            "candidate_id": candidate_id,
            "occurrence_id": str(getattr(occ, "occurrence_id", "")),
            "symbol": symbol,
            "timeframe": timeframe,
            "direction": str(occ.direction),
            "mode": mode,
            "role": role,
            "policy_id": policy_id,
            "decision_time": decision_time,
            "decision_status": "UNRESOLVED",
            "decision_reason": "",
            "anchor_a_time": "",
            "anchor_a_price": None,
            "anchor_a_confirmed_at": "",
            "anchor_b_time": "",
            "anchor_b_price": None,
            "anchor_b_confirmed_at": "",
            "levels_json": "{}",
            "matched_levels_json": "[]",
            "activated": 1 if getattr(occ.temporal_model, "entry_at", "") else 0,
            "activation_level": float(getattr(occ, "activation_level", 0.0) or 0.0),
            "entry_time": str(getattr(occ.temporal_model, "entry_at", "") or ""),
            "entry_price": float(getattr(occ, "entry_price", 0.0) or 0.0),
            "stop_price": float(getattr(occ, "initial_stop", 0.0) or 0.0),
            "target_outcomes_json": "{}",
            "last_observed_candle": "",
            "source": source,
            "is_test": 1 if is_synthetic else 0,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def _confirmed_time(df: pd.DataFrame, pivot: Optional[ConfirmedPivot]) -> str:
        if pivot is None:
            return ""
        idx = int(pivot.confirmed_at_index)
        if idx < 0 or idx >= len(df):
            return ""
        return str(df.iloc[idx].time)

    def _attach_pre_snapshot(
        self,
        record: Dict[str, Any],
        pre: Any,
        levels: Dict[float, float],
        df_closed: pd.DataFrame,
    ) -> None:
        record["decision_status"] = str(pre.status)
        record["decision_reason"] = str(pre.reason)
        record["levels_json"] = _json({str(float(k)): float(v) for k, v in levels.items()})
        record["matched_levels_json"] = _json([float(v) for v in pre.matched_levels])
        record["last_observed_candle"] = str(df_closed.iloc[-1].time)
        if pre.anchor_a is not None:
            record["anchor_a_time"] = str(pre.anchor_a.time or "")
            record["anchor_a_price"] = float(pre.anchor_a.price)
            record["anchor_a_confirmed_at"] = self._confirmed_time(df_closed, pre.anchor_a)
        if pre.anchor_b is not None:
            record["anchor_b_time"] = str(pre.anchor_b.time or "")
            record["anchor_b_price"] = float(pre.anchor_b.price)
            record["anchor_b_confirmed_at"] = self._confirmed_time(df_closed, pre.anchor_b)

    def _attach_post_snapshot_and_outcomes(
        self,
        record: Dict[str, Any],
        *,
        occ: Any,
        df_closed: pd.DataFrame,
        time_to_index: Dict[str, int],
    ) -> None:
        pattern_low = float(getattr(occ, "pattern_low", 0.0) or 0.0)
        pattern_high = float(getattr(occ, "pattern_high", 0.0) or 0.0)
        decision_time = record["decision_time"]
        record["last_observed_candle"] = str(df_closed.iloc[-1].time)

        if pattern_high <= pattern_low:
            record["decision_status"] = "INVALID_PATTERN"
            record["decision_reason"] = "PATTERN_RANGE_INVALID"
            return

        if occ.direction == "BULLISH":
            anchor_a, anchor_b = pattern_low, pattern_high
        else:
            anchor_a, anchor_b = pattern_high, pattern_low
        levels = mirrored_extension_levels(anchor_a, anchor_b)
        record["decision_status"] = "AVAILABLE"
        record["decision_reason"] = "PATTERN_RANGE_KNOWN_AT_DECISION"
        record["anchor_a_time"] = decision_time
        record["anchor_a_price"] = float(anchor_a)
        record["anchor_a_confirmed_at"] = decision_time
        record["anchor_b_time"] = decision_time
        record["anchor_b_price"] = float(anchor_b)
        record["anchor_b_confirmed_at"] = decision_time
        record["levels_json"] = _json({str(float(k)): float(v) for k, v in levels.items()})

        entry_time = str(getattr(occ.temporal_model, "entry_at", "") or "")
        entry_index = time_to_index.get(entry_time) if entry_time else None
        entry_price = float(getattr(occ, "entry_price", 0.0) or 0.0)
        stop = float(getattr(occ, "initial_stop", 0.0) or 0.0)

        if entry_index is None:
            outcomes = {
                str(float(level)): {"state": "NOT_ACTIVATED", "bars": None, "price": float(price)}
                for level, price in levels.items()
            }
        else:
            outcomes = _target_outcomes(
                df_closed,
                entry_index,
                str(occ.direction),
                entry_price,
                stop,
                levels,
            )
        record["target_outcomes_json"] = _json(outcomes)
