"""Event Bus implementation for Hagmartk."""

from __future__ import annotations

from typing import Callable, Dict, List

from .event import Event
from .subscriber import Subscriber


EventHandler = Callable[[Event], None]


class EventBus:
    """Synchronous event bus responsible for routing events to subscribers."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Subscriber]] = {}

    def subscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Subscribe a subscriber to events by name."""
        self._subscribers.setdefault(event_name, [])

        if subscriber not in self._subscribers[event_name]:
            self._subscribers[event_name].append(subscriber)

    def unsubscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Remove a subscriber from an event's subscription list."""
        if event_name not in self._subscribers:
            return

        self._subscribers[event_name] = [
            item
            for item in self._subscribers[event_name]
            if item is not subscriber
        ]

        if not self._subscribers[event_name]:
            del self._subscribers[event_name]

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers registered for its name."""
        for subscriber in list(self._subscribers.get(event.name, [])):
            subscriber.handle(event)

    def clear(self) -> None:
        """Clear all subscribers and event registrations."""
        self._subscribers.clear()
