from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class OrbPublicationDecision:
    allowed: bool
    reason: str
    score: float = 0.0


@dataclass(frozen=True)
class OrbPublicationConfig:
    max_roots_per_window: int = 3
    window_minutes: int = 15
    symbol_cooldown_minutes: int = 60
    min_liquidity_percentile: float = 70.0

    @classmethod
    def from_environment(cls) -> "OrbPublicationConfig":
        def integer(name: str, default: int, minimum: int) -> int:
            try:
                return max(minimum, int(os.getenv(name, str(default))))
            except ValueError:
                return default

        def number(name: str, default: float) -> float:
            try:
                return float(os.getenv(name, str(default)))
            except ValueError:
                return default
        return cls(
            max_roots_per_window=integer("HAGMARTK_ORB_TELEGRAM_MAX_ROOTS", 3, 1),
            window_minutes=integer("HAGMARTK_ORB_TELEGRAM_WINDOW_MINUTES", 15, 1),
            symbol_cooldown_minutes=integer("HAGMARTK_ORB_TELEGRAM_SYMBOL_COOLDOWN_MINUTES", 60, 1),
            min_liquidity_percentile=max(
                0.0,
                min(100.0, number("HAGMARTK_ORB_TELEGRAM_MIN_LIQUIDITY_PERCENTILE", 70.0)),
            ),
        )

    @property
    def lookback_minutes(self) -> int:
        return max(self.window_minutes, self.symbol_cooldown_minutes)


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


def _score(event: Mapping[str, Any]) -> float | None:
    try:
        value = float(event.get("liquidity_percentile_24h"))
    except (TypeError, ValueError):
        return None
    if value < 0.0 or value > 100.0:
        return None
    return value

def evaluate_orb_publication(
    event: Mapping[str, Any],
    recent_activity: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
    config: OrbPublicationConfig | None = None,
) -> OrbPublicationDecision:
    cfg = config or OrbPublicationConfig.from_environment()
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    score = _score(event)
    if score is None:
        return OrbPublicationDecision(False, "LIQUIDITY_UNAVAILABLE", 0.0)
    if score < cfg.min_liquidity_percentile:
        return OrbPublicationDecision(False, "LIQUIDITY_BELOW_PUBLICATION_THRESHOLD", score)

    symbol = str(event.get("symbol") or "").upper()
    signal_id = str(event.get("signal_id") or "")
    session_id = str(event.get("session_id") or "")
    rows = [dict(row) for row in recent_activity]

    for row in rows:
        if signal_id and str(row.get("event_id") or "") == signal_id:
            return OrbPublicationDecision(False, "DUPLICATE_SIGNAL_ID", score)
        if session_id and str(row.get("operation_key") or "") == f"ORB:{session_id}":
            return OrbPublicationDecision(False, "DUPLICATE_SESSION", score)

    window_start = current - timedelta(minutes=cfg.window_minutes)
    roots_in_window = 0
    cooldown_start = current - timedelta(minutes=cfg.symbol_cooldown_minutes)
    for row in rows:
        created_at = _parse_utc(row.get("created_at"))
        if created_at is None:
            continue
        if created_at >= window_start:
            roots_in_window += 1
        if symbol and str(row.get("symbol") or "").upper() == symbol and created_at >= cooldown_start:
            return OrbPublicationDecision(False, "SYMBOL_COOLDOWN_ACTIVE", score)

    if roots_in_window >= cfg.max_roots_per_window:
        return OrbPublicationDecision(False, "GLOBAL_PUBLICATION_BUDGET_EXCEEDED", score)
    return OrbPublicationDecision(True, "QUALIFIED_FOR_PUBLICATION", score)
