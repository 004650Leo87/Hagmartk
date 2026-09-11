# HAGMARTK DVP — Operational Timeframe Scope

Date: 2026-09-10
Status: FROZEN OPERATIONAL SCOPE
Project: HAGMARTK SHADOW

## Decision
The live/prospective DVP scanner operates only on:

`M15, M30, H1, H2, H4, D1, W1`

M5 is removed from the live DVP scanning universe. M5 remains supported only by the strategy engine for historical/replay compatibility and does not create new prospective DVP operations.

## Governance
This is an operational-universe change, not a strategy-math change. The frozen HDF candidate identity, version and parameter hash remain unchanged.

Historical M5 evidence is preserved. No historical event is deleted, rewritten as gain/stop, or republished to Telegram.

## Persisted scanner-state reconciliation
On scheduler startup, any persisted DVP scanner state outside the operational timeframe set is forced to:

- `enabled = false`
- `scanner_status = DISABLED`
- `error_message = OUT_OF_OPERATIONAL_TIMEFRAME_SCOPE`

At deployment validation, 801 persisted M5 scanner states were found and all 801 were disabled. No active M5 DVP operation remained.

## Runtime proof
After restart with the official HAGMARTK launcher flags:

- configured assets: 801
- configured combinations: 5607 (`801 x 7`)
- provider-supported instruments: 688
- monitored combinations: 4816 (`688 x 7`)
- API operational timeframes: `M15,M30,H1,H2,H4,D1,W1`
- API M5 scanner count: 0
- Telegram notifier: `ready=true`

ORB and HAGMARTK TDC scopes are independent and were not changed by this decision.
