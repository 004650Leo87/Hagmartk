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
