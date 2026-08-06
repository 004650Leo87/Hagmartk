"""Core exception types for Hagmartk.

Define explicit, structured exceptions for adapters and engines so callers
can react programmatically and logs surface actionable messages.
"""

from __future__ import annotations

from typing import Optional


class HagmartkError(Exception):
	"""Base class for all Hagmartk errors."""


class AdapterError(HagmartkError):
	"""Generic adapter-level error."""


class AdapterUnavailableError(AdapterError):
	"""Raised when a third-party library or external adapter is unavailable.

	Attributes:
		name: optional adapter name
		details: optional technical details to help debugging
	"""

	def __init__(self, message: str, name: Optional[str] = None, details: Optional[str] = None):
		super().__init__(message)
		self.name = name
		self.details = details


class AdapterConnectionError(AdapterError):
	"""Raised when an adapter fails to connect or authenticate."""


class EngineError(HagmartkError):
	"""Generic engine-level error."""


class EngineInitializationError(EngineError):
	"""Raised when an engine fails to initialize."""


class EngineShutdownError(EngineError):
	"""Raised when an engine fails to shutdown cleanly."""
