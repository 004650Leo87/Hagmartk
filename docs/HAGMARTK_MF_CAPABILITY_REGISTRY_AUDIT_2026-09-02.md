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
