"""Engine lifecycle status values for Hagmartk."""

from enum import Enum


class EngineStatus(str, Enum):
    """Explicit lifecycle states used by the Kernel and engines."""

    CREATED = "CREATED"
    REGISTERED = "REGISTERED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
