# HAGMARTK MF — HDF Event Radar V1 — 2026-09-03

Status: INTERNAL / READ-ONLY / NO PUBLICATION

## Scope

This gate connects the registered HDF Shadow evidence contract to the internal Market Event Protocol without promoting evidence to a publishable Quant Event.

Source evidence contract: `HDF_SHADOW_EVIDENCE_V1`.
Strategy contract: `hagmartk_divergence_flow` v1.0.0 / candidate `hdf_dvp_exit_2r`.

## Frozen behavior

- Accept only `LIVE_PROSPECTIVE`, non-test HDF evidence.
- Convert each accepted evidence row into one deterministic internal `RADAR` MarketEvent.
- Preserve persisted HDF stage exactly (`HDF_D`, `HDF_DV`, `HDF_DP`, `HDF_DVP`).
- Do not infer a later HDF stage.
- Do not create entry/reference region, invalidation or target structure.
- Keep `publication_eligible=false`.
- Do not enable real-order execution or external publishing.

## API

Read-only endpoint:

`GET /api/events/radar?limit=N`

Valid limit: 1..200.
POST, PUT and DELETE are not implemented and must return HTTP 405.

## Validation

- SQLite-temporary integration confirms only LIVE_PROSPECTIVE non-test evidence is projected.
- Repeated transformation of the same evidence produces the same `event_id`.
- `HDF_DV` remains RADAR with no trade structure.
- `HDF_DVP` also remains RADAR in Internal Event Engine V1; Quant promotion is separately gated.
- Directed Event Radar/Event Protocol suite: 26 PASS.
- Full project regression: **482 PASS, 1 expected skip, 0 failures**.

Next gate: validate the read-only endpoint against the real Shadow ledger. Any future Quant Event promotion requires a separate publication gate and is outside this V1.
