# HAGMARTK DVP — Fibonacci Prospective Telemetry V1 — 2026-09-03

Status: IMPLEMENTATION GATE / RESEARCH ONLY

## Objective

Observe Fibonacci policies prospectively in the existing Shadow universe without changing the frozen HDF candidate, emitting orders, or selecting a policy by realized outcome.

## Frozen universe

- Existing Shadow universe only: 13 assets x M15/H1/H4 = 39 combinations.
- No silent expansion to M5/M30/H2.
- Closed candles only.
- `shadow_started_at` is the live prospectivity boundary.

## Modes recorded

1. `PRE_REVERSAL_STRICT_V1`
   - role: `CONFLUENCE`
   - policy: latest valid confirmed leg strictly before reversal P2
   - decision state: PASS / FAIL / UNRESOLVED

2. `POST_REVERSAL_PATTERN_RANGE_V1`
   - role: `TARGET`
   - anchors: already-known reversal-pattern extremes
   - decision state: AVAILABLE or INVALID_PATTERN

## Anti-look-ahead contract

For each event/mode, the first inserted decision snapshot is immutable:

- decision time;
- policy/mode/role;
- anchor times, prices and confirmation times;
- projected levels;
- decision status;
- matched decision levels.

Later scans may update only observation fields that genuinely evolve after decision:

- activation flag/time/price;
- structural stop;
- per-level target outcome;
- bars to terminal outcome;
- last observed candle / update time.

No later scan may rewrite the original anchor pair because a different pair fits subsequent price action better.

## Independent deployment boundary

Fibonacci telemetry has its own persisted research-session T0: `HDF_FIBONACCI_RESEARCH_V1`.

For live rows, the effective admission boundary is the later of:

- the existing Shadow `shadow_started_at`; and
- the Fibonacci telemetry deployment T0.

This prevents events that occurred before the telemetry policy was deployed from being retroactively labeled `LIVE_PROSPECTIVE`, even when they occurred after the older Shadow session began.

Historical/replay validation must use an isolated database or explicit test override and must never populate the production live ledger.

## Isolated functional validation

Using the frozen 39-combination subset (13 assets x M15/H1/H4) and a temporary SQLite database:

- HDF_DVP occurrences observed: **65**.
- Expected telemetry rows: 65 events x 2 modes = **130**.
- Actual ledger rows: **130**.
- `PRE_REVERSAL_STRICT_V1`: 65 rows — 10 PASS, 55 FAIL.
- `POST_REVERSAL_PATTERN_RANGE_V1`: 65 rows — 65 AVAILABLE.
- Target states across 325 projected levels: 135 NOT_ACTIVATED, 133 STOP_FIRST, 57 TARGET_FIRST.
- Temporary database was removed after the check.

This is a functional harness, not prospective performance evidence.

Reproduction: `python tools/audit_fibonacci_prospective_telemetry.py`.

## Research-only evidence summary

The Fibonacci ledger now exposes a read-only research summary that reuses the central Shadow sample-size classification without importing historical expectancy or ROI assumptions into Fibonacci research.

Frozen thresholds reused only as collection-maturity labels:
- `<20`: `INSUFFICIENT`;
- `20-49`: `EARLY`;
- `50-99`: `USABLE`;
- `>=100`: `MATURE`.

`PRE_REVERSAL_STRICT_V1` uses independent decision snapshots as its maturity basis because its role is confluence qualification.
`POST_REVERSAL_PATTERN_RANGE_V1` uses resolved activated events because its role is target observation.

`promotion_allowed` is always `false`. The summary cannot alter candidate/version/hash, emit orders, or promote a Fibonacci policy.

## Live checkpoint after clock-integrity reset

Current live report immediately after the clean restart:
- scanner coverage: **1.0 / HEALTHY**;
- failed scanner checks: **0**;
- live Fibonacci records: **0**;
- both modes: `INSUFFICIENT`;
- reason codes include `RESEARCH_ONLY`, `NO_AUTOMATIC_PROMOTION`, `SCANNER_COVERAGE_HEALTHY`, and `NO_LIVE_FIBONACCI_EVENTS`.

Reproduction:

`python tools/report_fibonacci_research_status.py`

## Read-only API surface

The research summary is exposed internally through:

`GET /api/shadow/fibonacci-research`

The endpoint is GET-only and returns the same research object used by the CLI report. It has no mutation path, no promotion action and no order-execution capability.

Validation after adding the route: **129 passed, 1 skipped** across the service suite plus MT5 adapter tests.
