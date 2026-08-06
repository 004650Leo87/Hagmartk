"""Subscriber base class for Hagmartk Event Bus."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .event import Event


class Subscriber(ABC):
    """Abstract subscriber that consumes events from the Event Bus."""

    @abstractmethod
    def handle(self, event: Event) -> None:
        """Handle a published event."""

    @property
    @abstractmethod
    def subscribed_events(self) -> list[str]:
        """Return a list of event names this subscriber listens for."""
