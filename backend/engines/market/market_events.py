"""Market engine event definitions for Hagmartk."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from backend.eventbus.event import Event


@dataclass(frozen=True)
class MarketEngineStarted(Event):
    """Event emitted when the Market Engine starts successfully."""

    name: str = "MarketEngineStarted"
    payload: Dict[str, Any] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", self.payload or {})


@dataclass(frozen=True)
class MarketEngineStopped(Event):
    """Event emitted when the Market Engine shuts down."""

    name: str = "MarketEngineStopped"
    payload: Dict[str, Any] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", self.payload or {})
