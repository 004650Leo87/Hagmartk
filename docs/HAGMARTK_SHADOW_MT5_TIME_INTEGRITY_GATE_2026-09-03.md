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
