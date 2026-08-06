"""Base engine abstraction for Hagmartk."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .engine_status import EngineStatus


class BaseEngine(ABC):
    """Abstract base class that defines the engine contract."""

    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
        self.status = EngineStatus.CREATED

    @abstractmethod
    def initialize(self) -> None:
        """Initialize engine resources and prepare it for execution."""

    @abstractmethod
    def shutdown(self) -> None:
        """Release all engine resources and stop its execution."""
