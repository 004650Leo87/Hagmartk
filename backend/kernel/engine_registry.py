"""Registry for managing engine registration in Hagmartk."""

from typing import Dict, List

from backend.core.logger import logger

from .base_engine import BaseEngine
from .engine_status import EngineStatus


class EngineRegistry:
    """Simple registry responsible for registering and listing engines."""

    def __init__(self) -> None:
        self._engines: Dict[str, BaseEngine] = {}

    def register(self, engine: BaseEngine) -> None:
        """Register an engine instance by its unique name."""
        if engine.name in self._engines:
            raise ValueError(
                f"An engine with the name '{engine.name}' is already registered."
            )

        engine.status = EngineStatus.REGISTERED
        logger.info(
            "Engine registered: %s, version=%s",
            engine.name,
            engine.version,
        )

        self._engines[engine.name] = engine

    def get(self, name: str) -> BaseEngine | None:
        """Retrieve a registered engine by name."""
        return self._engines.get(name)

    def list_engines(self) -> List[BaseEngine]:
        """Return all registered engines in registration order."""
        return list(self._engines.values())
