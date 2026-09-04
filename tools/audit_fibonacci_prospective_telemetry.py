from collections import Counter
from pathlib import Path
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.fibonacci_prospective_telemetry import FibonacciProspectiveTelemetryEngine
from backend.services.shadow_store import ShadowStoreRepository
from backend.strategies.hdf.strategy import HDFStrategy

SNAPSHOT = ROOT / "data_cache" / "dvp_post_reversal_snapshot_20260903.csv"
DB = ROOT / "data_cache" / "fib_telemetry_functional_test.db"
SYMBOLS = ["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","NZDUSD","USDCAD","EURJPY","GBPJPY","XAUUSD","XAGUSD","BTCUSD","ETHUSD"]
TIMEFRAMES = ["M15", "H1", "H4"]

if DB.exists():
    DB.unlink()

snapshot = pd.read_csv(SNAPSHOT)
store = ShadowStoreRepository(str(DB))
engine = FibonacciProspectiveTelemetryEngine(store=store, started_at="2000-01-01T00:00:00+00:00")
written = 0
occ_count = 0
for symbol in SYMBOLS:
    for timeframe in TIMEFRAMES:
        df = snapshot[
            (snapshot.snapshot_symbol == symbol)
            & (snapshot.snapshot_timeframe == timeframe)
        ].copy()
        df = df.drop(columns=["snapshot_symbol", "snapshot_timeframe"]).reset_index(drop=True)
        strategy = HDFStrategy(variant="HDF_DVP")
        occurrences = strategy.evaluate_full_dataset_analysis(df, symbol, timeframe)["occurrences"]
        occ_count += len(occurrences)
        written += engine.process_occurrences(
            symbol=symbol,
            timeframe=timeframe,
            df_closed=df,
            occurrences=occurrences,
            strategy=strategy,
            shadow_started_at="2000-01-01T00:00:00+00:00",
            candidate_id="hdf_dvp_exit_2r",
            is_synthetic=False,
        )

rows = store.get_fibonacci_telemetry(source="LIVE_PROSPECTIVE", is_test=False, limit=10000)
print("OCCURRENCES", occ_count)
print("WRITTEN_CALLS", written)
print("LEDGER_ROWS", len(rows))
print("MODES", Counter(row["mode"] for row in rows))
print("DECISION_STATUS", Counter((row["mode"], row["decision_status"]) for row in rows))
target_states = Counter()
for row in rows:
    if row["mode"] != "POST_REVERSAL_PATTERN_RANGE_V1":
        continue
    outcomes = json.loads(row["target_outcomes_json"])
    for payload in outcomes.values():
        target_states[payload["state"]] += 1
print("TARGET_STATES", target_states)

assert len(rows) == occ_count * 2
assert Counter(row["mode"] for row in rows)["PRE_REVERSAL_STRICT_V1"] == occ_count
assert Counter(row["mode"] for row in rows)["POST_REVERSAL_PATTERN_RANGE_V1"] == occ_count

DB.unlink()
print("TEMP_DB_REMOVED", not DB.exists())
