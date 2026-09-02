# HAGMARTK MF — Product North

Status: governing product direction
Date: 2026-08-29

## Mission
HAGMARTK MF is a quantitative market-intelligence workstation. Its job is not to imitate a retail trading terminal. Its job is to ingest real market data, test strategies under explicit assumptions, discover repeatable market events, measure their evidence, monitor validated events in real time, and communicate what the engine knows — including uncertainty.

## Product doctrine
1. Evidence before interface.
2. No visible control without a tested backend contract.
3. No synthetic market fact may be presented as observed fact.
4. Research, validation, shadow monitoring and publication are distinct states.
5. Strategy optimization is forbidden before execution/data fidelity gates are satisfied.
6. The dashboard visualizes intelligence; it does not exist to reproduce TradingView.
7. Real-time outputs must always expose provenance, timestamp, symbol, timeframe, strategy/event version and confidence/evidence status.

## Core lifecycle
DATA -> NORMALIZE -> RESEARCH -> FIDELITY -> VALIDATE -> SHADOW -> EVENT -> MANAGE -> PUBLISH -> REVIEW

Every strategy or discovered event must move through this lifecycle. No stage may be skipped by UI action.

## Primary product surfaces
- Intelligence Cockpit: what the system currently sees and why it matters.
- Strategy Lab: deterministic strategy definitions, tests, robustness and parity evidence.
- Event Radar: ranked, real-time candidate events across symbols/timeframes.
- Evidence Inspector: sample size, regimes, failure cases, expectancy and data lineage.
- Live Event Desk: lifecycle of active events from detection to target/stop/invalidation.
- Research Queue: controlled experiments and automated scans awaiting validation.
- System Health: feeds, latency, stale data, broker/MT5 state, model assumptions and incidents.

## UI rule: Capability Registry
Every button/card/filter must map to a capability record with: capability_id, owner module, input contract, output contract, validation tests, allowed product stage, failure state, telemetry and evidence link. If any field is missing, the control stays hidden or disabled.

## Strategy/event object
A strategy is not a chart drawing. It is a versioned object containing hypothesis, exact rules, universe, timeframe, data requirements, execution assumptions, costs, tests, robustness results and release state.

An event is an immutable observation generated from a versioned strategy/event detector. It contains detection time, symbol, timeframe, trigger facts, planned invalidation/targets when applicable, evidence snapshot and subsequent lifecycle updates.

## Research engine direction
The long-term scanner searches symbol x timeframe x condition space for repeatable conditional behavior. Discovery is hypothesis generation only. Candidates must pass leakage checks, minimum sample, walk-forward/out-of-sample tests, regime analysis and execution-fidelity gates before becoming publishable events.

## Publication boundary
Telegram, social media, livestream overlays and future subscriber channels consume a read-only Publication API/Event Bus. They do not call strategy internals and cannot mutate research or trading state.

## Near-term build order
1. Finish Cycle Theory V111 fidelity and preserve HDF/DVP frozen contracts.
2. Inventory current dashboard controls and map them to real capabilities.
3. Remove, hide or relabel orphan/experimental controls.
4. Define Strategy Registry + Evidence Registry + Event schema.
5. Build Event Radar from validated/shadow outputs.
6. Build Live Event Desk and replayable event lifecycle.
7. Only then build Telegram/publication adapters and broadcast overlays.
8. Strategy-discovery automation follows after the validation pipeline can reject false discoveries reliably.

## Non-goals
- Rebuilding TradingView drawing/analysis ergonomics.
- Manual order-entry terminal features.
- Autonomous real-money execution in the current product stage.
- Black-box AI signals with no mathematical provenance.
- Performance claims based on modeled costs, modeled fills or insufficient samples.

## Broadcast-facing intelligence ideas
- Market Pulse: compact regime/volatility/liquidity state by asset class.
- Event Confidence Ladder: evidence grade, never a fabricated probability.
- Why Now: 3-5 machine facts that caused an event to surface.
- Event Timeline: detected -> confirmed -> target 1 -> target 2 -> invalidated/closed.
- Strategy Autopsy: after closure, show what matched and what failed.
- Research Live: controlled candidate scan with visible rejection reasons.
- Data Trust Strip: feed age, spread quality, server clock, assumptions and health.

## Monetization principle
Monetization is layered around verified information products and community access, not around hiding the quantitative truth. Free/public surfaces can show delayed or summarized intelligence; paid surfaces may offer deeper evidence, faster event lifecycle, specialized channels and research analytics. Exact commercial design requires later regulatory, platform-policy and market validation.

## Governance checkpoint
This document defines the product north. UI redesign, new capabilities and distribution integrations must be reviewed against it before implementation. Changes to the north require an explicit architecture decision record rather than ad-hoc UI work.

## Current research anchors
- HDF/DVP remains a frozen quantitative candidate family and must not be casually changed.
- Cycle Theory V111 remains research-only until the remaining fidelity/parity gates are bounded or proven.
- Additional named methods, including DIVAP, enter only after their exact public/source rules can be recovered and versioned without invention.

## MT5 runtime scope
For HAGMARTK MF, MT5 evidence and read-only integration are scoped to the currently authenticated Pepperstone terminal runtime whose data path is `73B7A2420D6397DFF9014A20F1201F97` and server is `Tickmill-Live`.
Other installed or running MT5 terminals are out of project scope and must not be queried, restarted, configured, or treated as evidence sources.
This scope does not authorize live order submission, cancellation, or position modification.

## Fidelity gate decision — 2026-09-02
Cycle Theory V111 reached the current safe read-only fidelity boundary. Remaining execution-sensitive gaps stay explicitly PARTIAL/MODELLED and do not authorize profitability claims or real trading. Product work may proceed to Capability Registry/dashboard inventory while V111 remains research/validation and frozen HDF remains unchanged. See docs/CYCLE_THEORY_V111_FIDELITY_BOUNDARY_2026-09-02.md.
