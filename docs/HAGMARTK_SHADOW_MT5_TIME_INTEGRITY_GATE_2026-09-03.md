# HAGMARTK SHADOW — MT5 Time Integrity Gate — 2026-09-03

Status: CRITICAL INTEGRITY REPAIR

## Evidence

Windows clock at audit: 2026-09-04 01:30 UTC (2026-09-03 22:30 America/Recife).

Live Tickmill-Live MT5 observation before normalization:

- MT5 tick encoded as 2026-09-04 04:30 UTC.
- M15 bars extended through 04:30 UTC.
- Measured offset versus Windows UTC: approximately +10,800 seconds (+3h).

Official MetaTrader 5 Python documentation states that received tick/bar times are UTC without shift. The observed terminal therefore violates the adapter's prior UTC assumption.

## Risk

The Shadow closed-candle filter compared MT5 timestamps to Windows UTC. With a +3h broker encoding, multiple not-yet-real UTC bars could survive because the old filter removed only the final forming bar.

This compromises prospectivity labels and time-based evidence integrity even when price calculations themselves are otherwise unchanged.

## Frozen repair decision

1. Add explicit `broker_time_offset_hours` to the scoped MT5 runtime configuration.
2. Default remains 0h for other runtimes/providers.
3. Tick/bar output is normalized back to UTC real.
4. Range-query UTC inputs are transformed into the broker-encoded clock before the MT5 call.
5. Closed-candle filtering must reject every candle whose close time is after `now`, not just one final row.
6. HDF live evidence must pass the Shadow T0 boundary; warmup/history cannot be written as LIVE_PROSPECTIVE.
7. Existing pre-fix LIVE HDF evidence is preserved but reclassified as historical, never deleted.
8. Reset the main Shadow prospectivity T0 after clock normalization because the prior live sample is not methodologically comparable.
9. Candidate `hdf_dvp_exit_2r` v1.0.0 and its parameter hash remain unchanged.

## Live normalization proof

With configured offset +3h:

- normalized quote time differed from Windows UTC by only ~4.5 seconds;
- raw M15 list ended at 01:30 UTC;
- the closed-candle filter correctly retained 01:15 as the latest closed bar;
- a one-hour range query returned bars only inside the requested normalized UTC window.

## Operational reset and clean restart

A second consistent SQLite backup was created immediately before the clock-integrity migration.

Pre-fix active prospective material was preserved, not deleted:
- 899 scanner telemetry rows archived to legacy tables;
- 615 prospective observations archived;
- 39 evidence transitions archived;
- 89 HDF evidence rows reclassified as `HISTORICAL_BACKFILL`.

The active Shadow session was restarted at **2026-09-04 01:40:49 UTC**.
The Fibonacci telemetry effective T0 is the later of its own deployment T0 and the active Shadow T0.

All 39 combinations were seeded with their latest already-closed normalized candle. No seeded timestamp was in the future.

## First post-reset prospective cycle

At the first clean cycle:
- 39 scanner combinations were active;
- 39 prospective observations were written;
- 1 new `LIVE_PROSPECTIVE` HDF evidence was detected (`USDCHF M15`, bearish, stage `HDF_DV`, detected at 01:45 UTC);
- Fibonacci research telemetry remained at 0 because no eligible DVP event had occurred yet;
- no scanner state was `ERROR`;
- no processed candle timestamp was in the future.

Scanner coverage initially appeared artificially degraded because M15 assigned four expected checks at the first check of each hour. This was corrected to count only M15 close boundaries that had actually elapsed, respecting a mid-hour Shadow T0.

After recalculation of the 39 active rows: **39 expected / 39 successful / 0 failed / coverage 1.0 / HEALTHY**.

Validation after the change: **126 passed, 1 skipped** across the service suite plus MT5 adapter tests. Remaining warnings are existing FastAPI/Starlette deprecations.
