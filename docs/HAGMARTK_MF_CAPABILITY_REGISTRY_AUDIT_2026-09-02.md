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
