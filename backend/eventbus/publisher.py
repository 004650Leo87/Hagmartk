"""Publisher base class for Hagmartk Event Bus."""

from __future__ import annotations

from .event import Event
from .event_bus import EventBus


class Publisher:
    """Lightweight publisher helper that emits events through an EventBus.

    Keep this class deliberately simple: concrete engines may override
    `publish` if they need instrumentation, but by default `publish`
    forwards events to the injected `EventBus`.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def publish(self, event: Event) -> None:
        """Publish an event to the bus."""
        if self._event_bus is None:
            return
        self._event_bus.publish(event)
