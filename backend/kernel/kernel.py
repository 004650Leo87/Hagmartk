"""Kernel orchestrator for Hagmartk engines."""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.core.logger import logger

from .base_engine import BaseEngine
from .engine_registry import EngineRegistry
from .engine_status import EngineStatus


class Kernel:
    """Kernel responsible for starting, stopping and coordinating engines.

    This class preserves clean architecture by orchestrating engine lifecycle
    transitions without exposing engine internals or dependencies between engines.
    It manages lifecycle safety, rollback, and health reporting separately from
    the engine implementation details.
    """

    def __init__(self, registry: EngineRegistry) -> None:
        self.registry = registry
        self.status = EngineStatus.STOPPED
        self.failure_reason: Optional[str] = None

    def register_engine(self, engine: BaseEngine) -> None:
        """Register a new engine with the kernel."""
        self.registry.register(engine)

    def start(self) -> None:
        """Start all registered engines in a controlled pipeline.

        The kernel performs safe startup and rolls back already initialized
        engines in case of failure. This protects the system from partial
        initialization states and improves long-term reliability.
        """
        if self.status in (
            EngineStatus.INITIALIZING,
            EngineStatus.RUNNING,
        ):
            logger.warning(
                "Kernel start requested while already %s.",
                self.status,
            )
            return

        self.status = EngineStatus.INITIALIZING
        self.failure_reason = None
        logger.info("Kernel startup initiated.")

        initialized_engines: List[BaseEngine] = []

        try:
            for engine in self.registry.list_engines():
                engine.status = EngineStatus.INITIALIZING
                logger.info(
                    "Initializing engine: %s, version=%s",
                    engine.name,
                    engine.version,
                )
                engine.initialize()
                engine.status = EngineStatus.RUNNING
                logger.info("Engine running: %s", engine.name)
                initialized_engines.append(engine)

            self.status = EngineStatus.RUNNING
            logger.info("Kernel started successfully.")

        except Exception as error:
            failed_engine = engine
            failed_engine.status = EngineStatus.FAILED
            self.failure_reason = str(error)
            logger.error(
                "Kernel startup failed at engine '%s': %s",
                failed_engine.name,
                error,
                exc_info=True,
            )
            self._rollback(initialized_engines)
            self.status = EngineStatus.FAILED
            raise

    def shutdown(self) -> None:
        """Shutdown all registered engines safely in reverse order.

        The shutdown operation attempts graceful engine teardown while preserving
        kernel state and logging any failures.
        """
        if self.status == EngineStatus.STOPPED:
            logger.info("Kernel shutdown requested but already stopped.")
            return

        if self.status == EngineStatus.STOPPING:
            logger.warning("Kernel shutdown already in progress.")
            return

        self.status = EngineStatus.STOPPING
        logger.info("Kernel shutdown initiated.")

        shutdown_errors: List[str] = []

        for engine in reversed(self.registry.list_engines()):
            if engine.status not in (
                EngineStatus.RUNNING,
                EngineStatus.INITIALIZING,
                EngineStatus.FAILED,
            ):
                logger.info(
                    "Skipping shutdown for engine '%s' with status %s.",
                    engine.name,
                    engine.status,
                )
                continue

            logger.info("Shutting down engine: %s", engine.name)
            engine.status = EngineStatus.STOPPING

            try:
                engine.shutdown()
                engine.status = EngineStatus.STOPPED
                logger.info("Engine stopped: %s", engine.name)
            except Exception as error:
                engine.status = EngineStatus.FAILED
                shutdown_errors.append(
                    f"{engine.name}: {error}",
                )
                logger.error(
                    "Engine '%s' shutdown failed: %s",
                    engine.name,
                    error,
                    exc_info=True,
                )

        if shutdown_errors:
            self.status = EngineStatus.FAILED
            self.failure_reason = "; ".join(shutdown_errors)
            logger.error(
                "Kernel shutdown completed with errors: %s",
                self.failure_reason,
            )
        else:
            self.status = EngineStatus.STOPPED
            self.failure_reason = None
            logger.info("Kernel shutdown completed successfully.")

    def _rollback(self, engines: List[BaseEngine]) -> None:
        """Rollback previously initialized engines in reverse order."""
        logger.warning(
            "Kernel rollback initiated for %d engine(s).",
            len(engines),
        )

        for engine in reversed(engines):
            logger.info("Rolling back engine: %s", engine.name)
            engine.status = EngineStatus.STOPPING

            try:
                engine.shutdown()
                engine.status = EngineStatus.STOPPED
                logger.info("Rollback stopped engine: %s", engine.name)
            except Exception as error:
                engine.status = EngineStatus.FAILED
                logger.error(
                    "Rollback failed for engine '%s': %s",
                    engine.name,
                    error,
                    exc_info=True,
                )

    def is_running(self) -> bool:
        """Return true if the kernel has successfully started."""
        return self.status == EngineStatus.RUNNING

    def engine_status(self, name: str):
        """Return the lifecycle status of a registered engine."""
        engine = self.registry.get(name)
        return engine.status if engine is not None else None

    def system_status(self) -> Dict[str, str]:
        """Return a summary of kernel and engine statuses."""
        return {
            "kernel": self.status,
            "failure_reason": self.failure_reason or "",
            "engines": {
                engine.name: engine.status
                for engine in self.registry.list_engines()
            },
        }
