# ORB — Opening Range 15M / Signal 5M / Target 2R — v1.0.0

## Identity
- Strategy ID: `ORB_OPENING_RANGE_15M_5M_2R`
- Version: `1.0.0`
- Display name: `ORB`
- Config hash: `c1db74b8f2380d1cfed7138f9b1c67fa26069ff5414129fdb61d100dd6af2277`
- Initial execution policy: PAPER / SIMULATION only.
- Real broker execution: disabled.

## Frozen signal contract
The first 15 minutes after explicit session reference `t0` form the opening range from exactly three conventional 5-minute candles. The range is frozen at t0+15m. Only B3..B10 may signal, corresponding to closes at +20, +25, +30, +35, +40, +45, +50 and +55 minutes. Long requires close >= H_OR + 1 tick. Short requires close <= L_OR - 1 tick. The first valid signal consumes the only opportunity for the session.

## Frozen risk / exit contract
Stop is one tick beyond the opposite side of the opening range. Target is one gross 2R target, rounded away from entry to the valid price grid. No strategic partials, trailing, breakeven, re-entry, reversal, pyramiding, martingale or position increase. Risk budget is 0.25% of allocated strategy equity before entry. Force exit is t0+120m.

## Current repository implementation
`backend/strategies/orb/` contains deterministic configuration, profile/calendar validation, opening-range construction, signal detection, entry TTL/preflight, linear-contract sizing, target/stop calculation, OHLC reference conflict resolution, append-only ledger primitives, state/idempotency primitives and trade metrics.

The conformance suite currently covers the principal A-U fixtures that are deterministic without a live broker, plus holiday/early-close, partial technical fill, restart/idempotency, post-entry data gap, protection failure and ambiguous DST handling.

## TradingView
`integrations/tradingview/ORB_v1_indicator.pine` is deliberately an **indicator**, not the canonical execution engine. It provides SIGNAL_CONFORMANCE and visual evidence on a conventional 5-minute chart using an explicit reference session and IANA timezone. It never pretends to reproduce a 5-second entry TTL, broker margin rules, real fills or canonical PnL.

The HAGMARTK engine remains the source of truth for execution conformance and statistics. TradingView deployment and Pine compiler validation require an authenticated TradingView session and are a later operational step.

## Not yet activated
This commit does not start an ORB Shadow scanner, does not publish Telegram alerts, does not create broker orders and does not change DVP/HDF or Cycle Theory candidates. Runtime integration will occur only after the local HAGMARTK worktree is reconciled and the full project test suite is run on the target machine.
