"""Diagnostic entrypoint for Hagmartk runtime.

Usage:
    python -m backend.run_system_diagnostic

The script creates the system in the adapter mode defined by the
`HAGMARTK_MARKET_ADAPTER` environment variable (default: mock), starts it,
prints diagnostic information, and then shuts it down.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime

from backend.bootstrap import create_system, start_system, shutdown_system
from backend.core.logger import logger


def main():
    adapter_mode = os.environ.get("HAGMARTK_MARKET_ADAPTER", "mock")

    print(f"Starting Hagmartk diagnostic (adapter={adapter_mode})")

    system = create_system(adapter_mode=adapter_mode)

    event_bus = system["event_bus"]
    application = system["application"]
    market_engine = system["market_engine"]

    try:
        start_system(system)

        status = application.system_status()

        print("Kernel status:", status.get("kernel"))
        print("Failure reason:", status.get("failure_reason"))
        print("Engines:")
        for name, s in status.get("engines", {}).items():
            print(f"  - {name}: {s}")

        print("Adapter mode:", system.get("adapter_mode"))
        print("EventBus ready: ", isinstance(event_bus, object))

        # If MT5 adapter requested, attempt to retrieve connection info and symbol count
        if (system.get("adapter_mode") or "mock").lower() == "mt5":
            try:
                adapter = market_engine.adapter
                # attempt to connect (this may raise)
                adapter.connect()
                symbols = adapter.get_symbols()
                print("MT5 connection: SUCCESS")
                print("Symbol count:", len(symbols))
            except Exception as error:
                print("MT5 connection: FAILED")
                print("Error:")
                traceback.print_exception(error, error, error.__traceback__, file=sys.stdout)

    finally:
        shutdown_system(system)


if __name__ == "__main__":
    main()
