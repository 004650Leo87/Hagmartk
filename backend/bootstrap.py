"""Controlled bootstrap for Hagmartk system.

This module provides programmatic functions to create and start a minimal
Hagmartk runtime suitable for diagnostics and controlled local runs. It
creates one `EventBus`, one `Application`/`Kernel`, selects the market adapter
based on `HAGMARTK_MARKET_ADAPTER` environment variable (defaults to 'mock'),
registers the `MarketEngine`, and starts the kernel.

API:
- `create_system(adapter_mode: Optional[str]) -> dict` - create components
- `start_system(system: dict) -> None` - starts the kernel
- `shutdown_system(system: dict) -> None` - shuts down the kernel

The module intentionally avoids automatic side-effects on import to remain
safe for unit tests and import-time analysis.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from backend.eventbus.event_bus import EventBus
from backend.kernel.application import Application
from backend.kernel.engine_status import EngineStatus
from backend.core.logger import logger


DEFAULT_ADAPTER = os.environ.get("HAGMARTK_MARKET_ADAPTER", "mt5")


def _choose_adapter(adapter_mode: Optional[str]):
    mode = (adapter_mode or os.environ.get("HAGMARTK_MARKET_ADAPTER") or "mock").lower()

    if mode == "mock":
        from backend.engines.market.market_adapter import MockMarketAdapter

        return MockMarketAdapter()

    if mode == "mt5":
        # Lazy import of MT5 adapter so environments without MT5 can import
        from backend.engines.market.mt5_market_adapter import MT5MarketAdapter

        return MT5MarketAdapter()

    raise ValueError(f"Unknown adapter mode '{mode}'. Valid: mock, mt5")


def create_system(adapter_mode: Optional[str] = None) -> Dict:
    """Create system components but do not start the kernel.

    Returns a dict with keys: `event_bus`, `application`, `market_engine`, `adapter_mode`.
    """
    event_bus = EventBus()
    application = Application()

    # determine chosen adapter mode at runtime (respect env changes)
    chosen_mode = (adapter_mode or os.environ.get("HAGMARTK_MARKET_ADAPTER") or DEFAULT_ADAPTER).lower()
    adapter = _choose_adapter(adapter_mode)

    # create engine lazily to avoid side-effects
    from backend.engines.market.market_engine import MarketEngine

    market_engine = MarketEngine(adapter=adapter, event_bus=event_bus)

    return {
        "event_bus": event_bus,
        "application": application,
        "market_engine": market_engine,
        "adapter_mode": chosen_mode,
    }


def start_system(system: Dict) -> None:
    """Register and start the kernel with the provided system dict."""
    application: Application = system["application"]
    market_engine = system["market_engine"]

    # register
    application.register_engine(market_engine)

    try:
        application.start()
        # Iniciar o scheduler autônomo do Shadow Scanner em background
        from backend.services.shadow_scanner import ShadowScannerManager
        scanner = system.get("shadow_scanner") or ShadowScannerManager()
        system["shadow_scanner"] = scanner
        scanner.start_auto_scheduler(adapter=market_engine.adapter, interval_seconds=10.0)
    except Exception as error:
        logger.error("Failed to start system: %s", error)
        raise


def shutdown_system(system: Dict) -> None:
    """Shutdown the kernel safely."""
    scanner = system.get("shadow_scanner")
    if scanner is not None and hasattr(scanner, "stop_auto_scheduler"):
        try:
            scanner.stop_auto_scheduler()
        except Exception:
            pass

    application: Application = system.get("application")

    if application is None:
        return

    try:
        application.shutdown()
    except Exception:
        logger.exception("Error during system shutdown")
