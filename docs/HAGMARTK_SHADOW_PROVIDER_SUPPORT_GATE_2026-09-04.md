# HAGMARTK Shadow — Provider Support Gate — 2026-09-04

Status: OPERATIONAL INTEGRITY / PROVIDER-AWARE

## Incident

The configured Shadow universe remains 13 assets x 3 timeframes = 39 combinations.
During live Event Radar validation, scanner coverage degraded because the current scoped MT5 provider catalog did not contain `BTCUSD` or `ETHUSD`.

Observed before correction:
- BTCUSD and ETHUSD candle requests returned provider symbol-not-found.
- Six configured crypto combinations accumulated repeated `MARKET_DATA_UNAVAILABLE` failures.
- Historical scanner telemetry remains preserved.
- Forex symbols that had intermittent failures later returned valid candles again.

This is a provider-capability mismatch, not evidence that the HDF candidate or scanner logic failed.

## Frozen correction

The configured research universe is not reduced or rewritten.
Runtime monitoring is now resolved against the provider's actual symbol catalog.

Provider support is persisted in `shadow_provider_support` with symbol, support state, reason and checked timestamp.

Rules:
- configured universe remains 39 combinations;
- provider-supported combinations are actively scanned;
- unsupported combinations are marked `UNSUPPORTED_BY_PROVIDER`;
- unsupported combinations do not generate recurring scanner-failure telemetry;
- their prior failures remain queryable and are not deleted;
- active coverage excludes provider-unsupported combinations from its numerator/denominator;
- combination-level telemetry still exposes their historical checks and failures;
- provider support is refreshed periodically, so a later available symbol can re-enter monitoring without changing the research universe.

For the current runtime catalog the expected operational shape is:
- configured combinations: **39**;
- provider-supported assets: **11**;
- provider-supported combinations: **33**;
- unsupported symbols: **BTCUSD, ETHUSD**;
- provider-unsupported combinations: **6**.

## Safety boundary

No HDF strategy parameter, candidate id/version/hash, entry rule, stop, target, Fibonacci policy or real-order permission is changed.

This gate changes operational observability only: a provider cannot be penalized forever for symbols it does not expose, while unsupported scope remains explicit instead of silently disappearing.

## Validation

- Provider support/service suite: **144 PASS**.
- Full project regression: **485 PASS, 1 expected skip, 0 failures**.
- Runtime application requires a real provider-support refresh after a database backup.

## Runtime refresh after backup

A post-backup provider refresh later in the same session changed the observed runtime capability:

- scoped terminal: `C:\Program Files\Pepperstone MetaTrader 5\terminal64.exe`;
- connected server: `Tickmill-Live`;
- BTCUSD and ETHUSD were again present in the provider catalog and visible;
- provider support resolved to **13/13 assets / 39/39 configured combinations**.

Therefore the earlier 33/39 state is retained as an observed incident state, not a permanent catalog assumption. Provider support is dynamic and must be measured, never hardcoded.

## Scanner telemetry V2

A second observability defect was isolated during this incident: polling retries ran every 3 seconds, but `expected_checks` represented candle-close slots. The old aggregation could therefore count many failures for one expected candle while recording success only once when a new candle was processed.

V2 semantics:
- expected checks remain candle-close slots;
- repeated failures inside an already-accounted slot are idempotent;
- recovery in that slot replaces one unresolved failure with success;
- polling frequency can no longer inflate the expected denominator;
- previous active telemetry was preserved in `legacy_pre_polling_telemetry_20260904` before the V2 active table was reset.

Migration preserved Shadow session T0, HDF evidence, Fibonacci telemetry, candidate identity and all strategy rules.

## Independent telemetry T0

Operational coverage now has its own `shadow_telemetry_session` T0, independent from the Shadow evidence session.

This prevents a coverage reset in the middle of an hour from inheriting expected M15/H1/H4 slots that occurred before the reset. H1 is expected only on hourly boundaries; H4 only on 4-hour UTC boundaries; M15 only on 15-minute boundaries.

This T0 affects observability counters only. It does not reset or reclassify HDF/Fibonacci evidence.
