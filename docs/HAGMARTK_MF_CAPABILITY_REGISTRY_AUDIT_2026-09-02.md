# HAGMARTK MF — Capability Registry Audit — 2026-09-02

Status: FIRST UI INVENTORY / PRODUCT NORTH STEP 2

## Rule
A visible navigation/control must correspond to a real, tested capability. Informational development/safety pages are not primary product capabilities and must not occupy main navigation merely because components exist.

## First-pass findings
- Cockpit/chart: KEEP — real candles, quotes, indicators, evidence and system state are wired.
- Mercado/Ativos: KEEP — real market catalog/watchlist APIs exist.
- Shadow Monitor: KEEP — substantial read-only/prospective APIs and evidence exist; frozen HDF scope remains unchanged.
- Estratégia HDF: KEEP — represents the frozen strategy/evidence surface.
- Centro de Alertas: KEEP FOR DEEP AUDIT — wired to shadow/event state but individual actions still require contract mapping.
- Configurações: KEEP FOR DEEP AUDIT — requires control-by-control verification.
- Backtest Lab: REMOVE FROM PRIMARY NAV — current page explicitly says non-operational and execution is disabled.
- IA Hagmartk: REMOVE FROM PRIMARY NAV — current page is an informational description, not an independently validated user capability.
- Automação / Safety: REMOVE FROM PRIMARY NAV — current page is static status/policy copy, not a control surface backed by a live safety contract.

## Decision
Hide the three non-capability pages from primary navigation now. Do not delete their components or backend/research code. Continue with a control-level registry of the remaining visible surfaces before further UI expansion.

## Second-pass correction — route truth
Code-level routing inspection found two primary-navigation labels that do not own the capability they claim:
- Centro de Alertas routes to `ShadowStrategiesView`, duplicating Shadow Monitor instead of a distinct alert-center contract. HIDE from primary navigation.
- Configurações routes to `StrategyCenterView`, duplicating Estratégia HDF instead of a settings contract. HIDE from primary navigation.

This is a No Fake UI correction: the underlying views remain intact, but duplicate labels cannot imply capabilities that do not exist.

## Top-command first control classification
KEEP pending registry completion: symbol selector, timeframe selector, HDF evidence trigger, RSI visibility, Shadow alert drawer, system/MT5 diagnostics. These are wired to real state/data flows.
PRESENTATION ONLY: theme and Zen mode are local UI preferences; they do not count as market-intelligence capabilities and require no backend promotion.
FOLLOW-UP REQUIRED: diagnostics popover contains literal presentation strings (including latency/status text) that must be checked against live telemetry before being allowed to represent observed facts.

## Third-pass correction — truth layer
Operational status display was audited against live contracts.
- System health no longer starts as `ONLINE`; initial state is `UNKNOWN` until `/system/health` responds.
- MT5 connectivity is derived only from `adapter_connected` / `terminal_status` from the health endpoint.
- Broker/company label is displayed only when returned by live health telemetry.
- The fabricated `HTTP 200 OK (0.001ms)` text was removed. The UI now shows API availability from the successful health payload and displays measured `latency_ms` only as the backend's symbol-read latency, with an explicit label.
- The bottom Positions/Orders/History/Logs drawer was removed from the visible product surface because its contents were static statements, not live broker-backed data. The compact truthful status strip remains.

Decision: no operational fact may be inferred from a different subsystem's status, and no empty/static drawer may impersonate a live capability.

## Runtime truth correction — scoped MT5 launcher
The dedicated HAGMARTK MF launcher previously allowed backend startup without an explicit market-adapter mode, which permitted the runtime to come up on the mock adapter despite the frozen MT5 runtime scope.

Correction:
- `START_HAGMARTK_MF.ps1` now explicitly sets `HAGMARTK_MARKET_ADAPTER=mt5`.
- `MT5MarketAdapter` loads `config/mt5_runtime_scope.json` and initializes the scoped terminal executable directly.
- Adapter connection rejects a server mismatch instead of silently accepting another installed MT5 runtime.
- Read-only validation observed Pepperstone Group Limited, build 6140, 117 symbols, with the frozen Tickmill-Live server scope.
- Full suite after correction: 386 passed, 1 skipped, 0 failed.

This converts MT5 identity from an environmental assumption into an enforced runtime contract.
