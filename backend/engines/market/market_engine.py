"""Market Engine implementation for Hagmartk."""

from __future__ import annotations

from typing import Optional

from backend.eventbus.event_bus import EventBus
from backend.eventbus.publisher import Publisher
from backend.eventbus.event import Event
from backend.kernel.base_engine import BaseEngine
from backend.kernel.engine_status import EngineStatus
from backend.kernel.application import Application
from backend.core.exceptions import EngineInitializationError
from typing import Optional

from .market_adapter import MarketAdapter, MockMarketAdapter
from .market_events import MarketEngineStarted, MarketEngineStopped


class MarketEngine(BaseEngine, Publisher):
    """Market Engine responsible for market data lifecycle and event publication."""

    def __init__(
        self,
        adapter: Optional[MarketAdapter] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        BaseEngine.__init__(self, name="MarketEngine", version="0.1.0")
        Publisher.__init__(self, event_bus or EventBus())
        self.adapter = adapter or MockMarketAdapter()
        # Use BaseEngine.status as the single source of truth
        self.status = EngineStatus.CREATED

    def initialize(self) -> None:
        """Initialize the Market Engine and publish a start event."""
        self.status = EngineStatus.INITIALIZING

        try:
            self.adapter.connect()
            # Load full symbol catalog from adapter for quick access
            try:
                self.symbols = self.adapter.get_symbols()
            except Exception:
                self.symbols = []
        except Exception as error:
            # Wrap low-level adapter errors to provide actionable context
            raise EngineInitializationError(f"MarketEngine failed to initialize: {error}") from error

        self.status = EngineStatus.RUNNING
        self.publish_market_event(MarketEngineStarted(payload={"status": str(self.status)}))

    def shutdown(self) -> None:
        """Shutdown the Market Engine and publish a stop event."""
        self.status = EngineStatus.STOPPING

        try:
            self.adapter.disconnect()
        except Exception as error:
            # Do not raise during shutdown; record failed status and emit event
            self.status = EngineStatus.FAILED
            self.publish_market_event(MarketEngineStopped(payload={"status": str(self.status), "error": str(error)}))
            return

        self.status = EngineStatus.STOPPED
        self.publish_market_event(MarketEngineStopped(payload={"status": str(self.status)}))

    def get_status(self) -> EngineStatus:
        """Return the current lifecycle status of the Market Engine."""
        return self.status

    def publish_market_event(self, event: Event) -> None:
        """Publish a market event to the Event Bus."""
        self.publish(event)

    def publish(self, event: Event) -> None:
        """Publish an Event through the Event Bus."""
        if self._event_bus is not None:
            self._event_bus.publish(event)

    def initialize_kernel_registration(self, application: Application) -> None:
        """Register this engine with the provided Kernel application."""
        application.register_engine(self)
