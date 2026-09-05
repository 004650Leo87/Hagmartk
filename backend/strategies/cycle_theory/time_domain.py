"""Explicit time-domain policy for Cycle Theory V111 research/validation.

V111 uses broker-server wall clock (TimeCurrent/iTime). HAGMARTK market adapters
normalize the scoped MT5 feed to real UTC. This module performs the reverse
mapping explicitly before V111 replay; it never silently strips a timezone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class CycleTheoryBrokerClock:
    offset_hours: float
    policy_id: str = "SCOPED_MT5_BROKER_WALL_CLOCK_V1"

    @classmethod
    def from_runtime_scope(cls, scope: Mapping[str, Any]) -> "CycleTheoryBrokerClock":
        raw = scope.get("broker_time_offset_hours")
        if raw is None:
            raise ValueError("Cycle Theory requires explicit broker_time_offset_hours")
        try:
            offset = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid broker_time_offset_hours") from exc
        if abs(offset) > 14:
            raise ValueError("broker_time_offset_hours must be between -14 and +14")
        return cls(offset_hours=offset)

    @property
    def offset(self) -> timedelta:
        return timedelta(hours=self.offset_hours)

    def utc_to_server_naive(self, value: datetime) -> datetime:
        """Convert an aware UTC/offset datetime to naive V111 server wall time."""
        if value.tzinfo is None:
            raise ValueError("UTC source datetime must be timezone-aware")
        utc_value = value.astimezone(timezone.utc)
        return (utc_value + self.offset).replace(tzinfo=None)

    def iso_utc_to_server_naive(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return self.utc_to_server_naive(parsed)

    def server_naive_to_utc(self, value: datetime) -> datetime:
        """Convert naive V111 server wall time back to aware real UTC."""
        if value.tzinfo is not None:
            raise ValueError("Server wall-clock datetime must be naive")
        return (value - self.offset).replace(tzinfo=timezone.utc)

    def metadata(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "broker_time_offset_hours": self.offset_hours,
            "mql5_timecurrent_directly_proven": False,
        }
