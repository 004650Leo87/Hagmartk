from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import Any, Mapping


@dataclass(frozen=True)
class PublicationDecision:
    allowed: bool
    reason: str


def _parse_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _max_root_age_seconds() -> float:
    raw = os.getenv("HAGMARTK_TELEGRAM_ROOT_MAX_AGE_SECONDS", "900")
    try:
        return max(30.0, float(raw))

    except ValueError:
        return 900.0


def _fresh(value: Any, now: datetime | None = None) -> bool:
    event_time = _parse_utc(value)
    if event_time is None:
        return False
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age = (current - event_time).total_seconds()
    return -30.0 <= age <= _max_root_age_seconds()


def _positive(value: Any) -> bool:
    try:
        return float(value) > 0.0
    except (TypeError, ValueError):
        return False


def _present(mapping: Mapping[str, Any], *keys: str) -> bool:
    return all(mapping.get(key) not in (None, "", [], {}) for key in keys)


def evaluate_dvp_root(event: Any, now: datetime | None = None) -> PublicationDecision:
    metadata = dict(getattr(event, "metadata", {}) or {})
    if metadata.get("bootstrap_detected") or metadata.get("synthetic"):
        return PublicationDecision(False, "NON_PROSPECTIVE_EVENT")

    event_time = (
        getattr(event, "processed_at", "")
        or getattr(event, "received_at", "")
        or getattr(event, "updated_at", "")
        or getattr(event, "created_at", "")
    )
    if not _fresh(event_time, now):
        return PublicationDecision(False, "STALE_OR_INVALID_ROOT_TIME")
    evidence = dict(getattr(event, "evidence", {}) or {})
    numeric_values = (
        evidence.get("pivot_1_price", getattr(event, "pivot_1_price", 0)),
        evidence.get("pivot_2_price", getattr(event, "pivot_2_price", 0)),
        evidence.get("relative_volume", getattr(event, "relative_volume", 0)),
        getattr(event, "entry_price", 0) or getattr(event, "activation_level", 0),
        getattr(event, "initial_stop", 0),
        getattr(event, "target_2R", 0),
    )
    if not all(_positive(value) for value in numeric_values):
        return PublicationDecision(False, "DVP_EVIDENCE_INCOMPLETE")
    pivot_1_time = evidence.get("pivot_1_time", getattr(event, "pivot_1_time", ""))
    pivot_2_time = evidence.get("pivot_2_time", getattr(event, "pivot_2_time", ""))
    pattern = str(
        evidence.get("pattern_type", getattr(event, "pattern_type", "NONE"))
    ).upper()
    if not pivot_1_time or not pivot_2_time or pattern in {"", "NONE"}:
        return PublicationDecision(False, "DVP_EVIDENCE_INCOMPLETE")

    return PublicationDecision(True, "QUALIFIED_DVP_ROOT")


def evaluate_orb_root(
    event: Mapping[str, Any],
    now: datetime | None = None,
) -> PublicationDecision:
    if not _fresh(event.get("event_time"), now):
        return PublicationDecision(False, "STALE_OR_INVALID_ROOT_TIME")
    required = (
        "symbol", "signal_id", "signal_time", "t0",
        "range_high", "range_low", "entry", "stop", "target",
    )
    if not _present(event, *required):
        return PublicationDecision(False, "ORB_EVIDENCE_INCOMPLETE")
    for key in ("range_high", "range_low", "entry", "stop", "target"):
        if not _positive(event.get(key)):
            return PublicationDecision(False, "ORB_EVIDENCE_INCOMPLETE")
    if float(event["range_high"]) <= float(event["range_low"]):
        return PublicationDecision(False, "ORB_RANGE_INVALID")
    return PublicationDecision(True, "QUALIFIED_ORB_ROOT")
