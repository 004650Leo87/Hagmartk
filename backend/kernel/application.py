"""Hagmartk Kernel application entrypoint.

This module provides a lightweight application wrapper around the Kernel and
EngineRegistry. It is responsible for bootstrapping the system and managing
engine registration and lifecycle operations.
"""

from .engine_registry import EngineRegistry
from .kernel import Kernel
from .base_engine import BaseEngine


class Application:
    """Application entrypoint for the Hagmartk Kernel."""

    def __init__(self) -> None:
        self.engine_registry = EngineRegistry()
        self.kernel = Kernel(self.engine_registry)

    def register_engine(self, engine: BaseEngine) -> None:
        """Register a new engine with the application."""
        self.kernel.register_engine(engine)

    def start(self) -> None:
        """Start all registered engines through the kernel."""
        self.kernel.start()

    def shutdown(self) -> None:
        """Shutdown all registered engines through the kernel."""
        self.kernel.shutdown()

    def list_engines(self) -> list[BaseEngine]:
        """Return a list of all registered engines."""
        return self.engine_registry.list_engines()

    def is_running(self) -> bool:
        """Return true when the kernel is currently running."""
        return self.kernel.is_running()

    def engine_status(self, name: str):
        """Return the lifecycle status of a registered engine."""
        return self.kernel.engine_status(name)

    def system_status(self):
        """Return the current kernel and engine health status."""
        return self.kernel.system_status()
