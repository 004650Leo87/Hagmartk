from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.fibonacci_prospective_telemetry import FibonacciProspectiveTelemetryEngine
from backend.services.shadow_store import ShadowStoreRepository


def main() -> None:
    store = ShadowStoreRepository(str(ROOT / "data_cache" / "shadow_engine.db"))
    engine = FibonacciProspectiveTelemetryEngine(store=store)
    summary = engine.build_research_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
