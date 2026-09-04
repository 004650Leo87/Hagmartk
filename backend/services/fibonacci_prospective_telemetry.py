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
EVIDENCE_SNAPSHOT_SCHEMA = "HDF_FIB_DECISION_EVIDENCE_V1"


def _telemetry_id(symbol: str, timeframe: str, direction: str, decision_time: str, mode: str, source: str) -> str:
    raw = "|".join([symbol, timeframe, direction, decision_time, mode, source])
    return "fibtele_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _enum_value(value: Any) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


def _candle_snapshot(row: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key in ("time", "open", "high", "low", "close", "tick_volume", "real_volume", "volume"):
        if key not in row.index:
            continue
        value = row[key]
        if key == "time":
            payload[key] = str(value)
        else:
            try:
                payload[key] = float(value)
            except (TypeError, ValueError):
                payload[key] = str(value)
    return payload


def _decision_evidence_snapshot(strategy: Any, occ: Any, df: pd.DataFrame, decision_index: int) -> Dict[str, Any]:
    from backend.domain.candidate import HDF_CANDIDATE_V1_PARAMETER_HASH

    current = _candle_snapshot(df.iloc[decision_index])
    previous = _candle_snapshot(df.iloc[decision_index - 1]) if decision_index > 0 else {}
    return {
        "schema_version": EVIDENCE_SNAPSHOT_SCHEMA,
        "candidate_parameter_hash": HDF_CANDIDATE_V1_PARAMETER_HASH,
        "strategy_id": str(getattr(strategy, "strategy_id", "")),
        "strategy_version": str(getattr(strategy, "version", "")),
        "strategy_variant": str(getattr(strategy, "variant", "")),
        "occurrence_id": str(getattr(occ, "occurrence_id", "")),
        "occurrence_state": _enum_value(getattr(occ, "state", "")),
        "pattern_type": _enum_value(getattr(occ, "pattern_type", "")),
        "pattern_low": float(getattr(occ, "pattern_low", 0.0) or 0.0),
        "pattern_high": float(getattr(occ, "pattern_high", 0.0) or 0.0),
        "relative_volume": float(getattr(occ, "relative_volume", 0.0) or 0.0),
        "activation_level": float(getattr(occ, "activation_level", 0.0) or 0.0),
        "initial_stop": float(getattr(occ, "initial_stop", 0.0) or 0.0),
        "entry_at": str(getattr(getattr(occ, "temporal_model", None), "entry_at", "") or ""),
        "decision_candle": current,
        "previous_candle": previous,
    }


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

            evidence_snapshot_json = _json(
                _decision_evidence_snapshot(strategy, occ, df_closed, decision_index)
            )

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
            pre_record["evidence_snapshot_json"] = evidence_snapshot_json
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
            post_record["evidence_snapshot_json"] = evidence_snapshot_json
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
            "evidence_snapshot_json": "{}",
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


    def build_research_summary(
        self,
        candidate_id: str = "hdf_dvp_exit_2r",
        *,
        source: str = "LIVE_PROSPECTIVE",
        is_test: bool = False,
    ) -> Dict[str, Any]:
        """Read-only research summary; never promotes or mutates candidate state."""
        from collections import Counter
        from backend.services.shadow_intelligence import SAMPLE_SIZE_THRESHOLDS, classify_sample_size

        rows = self.store.get_fibonacci_telemetry(
            source=source,
            is_test=is_test,
            limit=100000,
        )
        scanner = self.store.get_shadow_telemetry(candidate_id=candidate_id).get("global", {})
        coverage = scanner.get("coverage")
        health = scanner.get("health", "UNKNOWN")

        def snapshot_attested(row: Dict[str, Any]) -> bool:
            try:
                payload = json.loads(row.get("evidence_snapshot_json") or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                return False
            return payload.get("schema_version") == EVIDENCE_SNAPSHOT_SCHEMA

        pre_rows = [row for row in rows if row.get("mode") == PRE_MODE]
        pre_by_occurrence = {str(row.get("occurrence_id", "")): row for row in pre_rows}
        unattested_total = sum(1 for row in rows if not snapshot_attested(row))

        modes: Dict[str, Any] = {}
        for mode, role in ((PRE_MODE, "CONFLUENCE"), (POST_MODE, "TARGET")):
            mode_rows = [row for row in rows if row.get("mode") == mode]
            attested_rows = [row for row in mode_rows if snapshot_attested(row)]
            decision_counts = Counter(str(row.get("decision_status", "")) for row in mode_rows)
            activated = sum(1 for row in mode_rows if int(row.get("activated") or 0) == 1)
            resolved_events = 0
            pending_events = 0
            ambiguous_events = 0
            level_states: Dict[str, Counter] = {}
            excluded = Counter()
            cohort_eligible_records = 0

            if mode == POST_MODE:
                eligible_rows = []
                for row in mode_rows:
                    if not snapshot_attested(row):
                        excluded["UNATTESTED_SNAPSHOT"] += 1
                        continue
                    pre_row = pre_by_occurrence.get(str(row.get("occurrence_id", "")))
                    if pre_row is None:
                        excluded["PRE_RECORD_MISSING"] += 1
                        continue
                    if not snapshot_attested(pre_row):
                        excluded["PRE_UNATTESTED_SNAPSHOT"] += 1
                        continue
                    if str(pre_row.get("decision_status", "")) != "PASS":
                        excluded["PRE_GATE_NOT_PASS"] += 1
                        continue
                    if int(row.get("activated") or 0) != 1:
                        excluded["NOT_ACTIVATED"] += 1
                        continue
                    eligible_rows.append(row)

                cohort_eligible_records = len(eligible_rows)
                for row in eligible_rows:
                    outcomes = json.loads(row.get("target_outcomes_json") or "{}")
                    states = [str(payload.get("state", "")) for payload in outcomes.values()]
                    if any(state == "AMBIGUOUS_SAME_BAR" for state in states):
                        ambiguous_events += 1
                    if any(state == "PENDING" for state in states):
                        pending_events += 1
                    elif states:
                        resolved_events += 1
                    for level, payload in outcomes.items():
                        if level not in level_states:
                            level_states[level] = Counter()
                        level_states[level][str(payload.get("state", ""))] += 1

                maturity_count = resolved_events
                maturity_basis = "RESOLVED_ACTIVATED_PRE_PASS_ATTESTED_EVENTS"
            else:
                cohort_eligible_records = len(attested_rows)
                if len(attested_rows) < len(mode_rows):
                    excluded["UNATTESTED_SNAPSHOT"] = len(mode_rows) - len(attested_rows)
                maturity_count = len(attested_rows)
                maturity_basis = "ATTESTED_DECISION_SNAPSHOTS"

            sample_class = classify_sample_size(maturity_count)
            modes[mode] = {
                "role": role,
                "records": len(mode_rows),
                "attested_records": len(attested_rows),
                "unattested_records": len(mode_rows) - len(attested_rows),
                "decision_status_counts": dict(decision_counts),
                "activated_records": activated,
                "cohort_eligible_records": cohort_eligible_records,
                "cohort_excluded_counts": dict(excluded),
                "resolved_events": resolved_events,
                "pending_events": pending_events,
                "ambiguous_events": ambiguous_events,
                "maturity_count": maturity_count,
                "maturity_basis": maturity_basis,
                "sample_class": sample_class,
                "target_level_states": {level: dict(counter) for level, counter in sorted(level_states.items())},
            }

        reason_codes = ["RESEARCH_ONLY", "NO_AUTOMATIC_PROMOTION"]
        if coverage is None:
            reason_codes.append("SCANNER_COVERAGE_UNKNOWN")
        elif coverage < 0.95:
            reason_codes.append("SCANNER_COVERAGE_DEGRADED")
        else:
            reason_codes.append("SCANNER_COVERAGE_HEALTHY")
        if not rows:
            reason_codes.append("NO_LIVE_FIBONACCI_EVENTS")
        if unattested_total:
            reason_codes.append("UNATTESTED_LEGACY_RECORDS")
        if rows and modes.get(POST_MODE, {}).get("cohort_eligible_records", 0) == 0:
            reason_codes.append("NO_ELIGIBLE_TARGET_COHORT")

        return {
            "research_scope": RESEARCH_SCOPE,
            "candidate_id": candidate_id,
            "research_state": "RESEARCH_ONLY",
            "promotion_allowed": False,
            "sample_thresholds": dict(SAMPLE_SIZE_THRESHOLDS),
            "scanner": {
                "coverage": coverage,
                "health": health,
                "failed_checks": scanner.get("failed_checks", 0),
            },
            "total_records": len(rows),
            "modes": modes,
            "reason_codes": reason_codes,
        }
