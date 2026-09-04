# HAGMARTK HDF Evidence Immutability Gate — 2026-09-04

## Problem found

A live USDCHF M15 research occurrence exposed a semantic inconsistency between `shadow_hdf_evidence` and Fibonacci research telemetry.

The investigation proved that `HDFEvidence` used an UPSERT keyed by symbol/timeframe/pivot/direction that rewrote decision-time fields on later rescans. Fields such as relative volume, pattern status, HDF stage, candidate flag and armed flag could therefore change after the original decision.

The existing Fibonacci rows also lacked a complete immutable decision-evidence snapshot, so their original generating state could not be independently reconstructed.

## Decision

Decision-time evidence is now append-only.

`shadow_hdf_evidence` no longer rewrites an existing logical evidence row. A later rescan cannot downgrade or upgrade the original HDF decision snapshot.

New Fibonacci telemetry stores `HDF_FIB_DECISION_EVIDENCE_V1`, including candidate hash, strategy identity, occurrence state, pattern, volume, activation/stop data, decision candle and previous candle.

TARGET maturity is allowed only when its matching PRE record is attested and has `decision_status=PASS`.

## Clean prospective boundary

The broader Shadow session was not reset. Its T0 remains `2026-09-04 01:40:49 UTC`.

A separate HDF evidence session was created with T0 `2026-09-04 10:04:59 UTC`. The Fibonacci research session was reset to the same timestamp so neither subsystem can repopulate pre-gate decisions as new live evidence after warmup or restart.

Existing records were preserved and reclassified:
- 3 HDF rows → `LEGACY_PRE_DECISION_IMMUTABILITY`;
- 2 Fibonacci rows → `LEGACY_PRE_ATTESTATION`.

No legacy row is counted as current live approval evidence.

## Validation

Targeted integrity suite: 17 PASS.
Expanded Shadow/Fibonacci suite before the T0 addition: 34 PASS.
Full project regression after all changes: **494 PASS, 1 skipped**.

Consistent SQLite backup created before migration:
`data_cache/shadow_engine_pre_evidence_integrity_20260904_100415.db`
SHA256: `f4eb0074cdfeafedcb7ed6bfe17a7749054287f0a881bc19cb4bb95c9a3a2d5d`.

The candidate `hdf_dvp_exit_2r` remains Shadow-only; no candidate parameters, version, publication permission or execution permission were changed by this gate.
