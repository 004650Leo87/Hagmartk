# CYCLE THEORY V111 — VALIDATION DECISION — 2026-09-04

Status: VALIDATION / NO LIVE ORDER EXECUTION

## Frozen identity

- Strategy: `cycle_theory_v111_fidelity`
- Source version: `111.00`
- Validation candidate: `cycle_theory_v111_baseline`
- Candidate version: `1.0.0`
- Source SHA-256: `32814ecf0a1ca6577f93d99e1bab358f92eed875314bc5c180ca77bc769096a2`
- Parameter hash: `a538c37c26282ab62e36ce1c1c5c826e11aee2370c8ed4ecffdaba7f145ccf85`
- Frozen source inputs: 30/30 original V111 inputs.
- Real-order execution: forbidden.

## Data/time integrity closed in this gate

The scoped MT5 feed is normalized to real UTC, then explicitly converted back to the V111 broker-server wall clock using the configured Tickmill-Live offset (+3h). Silent timezone stripping is rejected. Historical validation excludes the candle still in formation.

Observed Bid/Ask tick replay is now available through the same V111 state machine. It removes the deterministic OHLC intrabar path assumption, but does not claim server acceptance, slippage, commission or swap fidelity.

## Broad OHLC screening

The first validation matrix evaluated 13 configured assets across M5, M15, M30, H1, H2 and H4, using 1,500 closed candles per combination.

- combinations completed: 78/78;
- combinations with at least one completed trade: 65;
- positive-expectancy combinations among those with trades: 41;
- no real order was sent.

The strongest first-window results were not accepted at face value. The top candidates were replayed in three non-overlapping 1,500-bar windows with the same frozen parameters.

Four combinations were positive in all 3 OHLC windows:

| Combination | Trades | Net R | Weighted expectancy | Worst window |
|---|---:|---:|---:|---:|
| XAUUSD M30 | 111 | +33.3643 | +0.3006R | +0.1354R |
| EURUSD H2 | 61 | +11.9988 | +0.1967R | +0.0600R |
| GBPUSD H2 | 60 | +11.3997 | +0.1900R | +0.0505R |
| GBPJPY H4 | 112 | +18.5880 | +0.1660R | +0.1177R |

## Timeframe viability

The original V111 uses `PERIOD_CURRENT`, starts its daily operating window at 01:00 server time, stops new entries at 23:00, closes all activity at 23:50, and needs five bars before a channel can be defined.

Consequences under the unmodified V111 rules:

- M1 through H4 can form the required five-bar channel inside the daily window;
- D1 and W1 cannot accumulate five bars before the daily close/reset;
- 13/13 D1 screening combinations produced zero trades;
- 13/13 W1 screening combinations produced zero trades.

This is a structural property of V111, not a scanner failure. D1/W1 must not be marketed as operational timeframes unless a separately versioned strategy changes the original schedule/channel rules.

M1 was also screened separately. Eleven provider-supported combinations generated trades. Only USDJPY M1 remained positive in all three non-overlapping OHLC windows: 38 trades, +3.4481R, weighted expectancy +0.0907R.

## Observed-tick evidence

The tick gate replays the same state machine using chronological MT5 Bid/Ask ticks. This materially changed several OHLC conclusions.

### XAUUSD M30

Three independent 120-bar tick windows produced:

- offset 0: 5 trades, -0.1289R, expectancy -0.0258R;
- offset 120: 3 trades, +1.8345R, expectancy +0.6115R;
- offset 240: 5 trades, -1.8620R, expectancy -0.3724R.

Aggregate: 13 completed tick-backed trades, approximately -0.1565R before commission/slippage. The OHLC champion does not survive this execution-fidelity gate and is rejected for promotion.

### EURUSD H2

- offset 0: 1 trade, -0.2574R;
- offset 120: 2 trades, -0.4021R;
- offset 240: 0 tick-backed trades.

Aggregate: 3 trades, -0.6595R. The available tick evidence does not support promotion.

### GBPUSD H2

Three recent 120-bar tick windows produced:

- offset 0: 1 trade, +0.8893R;
- offset 120: 2 trades, +0.1538R;
- offset 240: 0 tick-backed trades.

Aggregate: 3 trades, +1.0431R. Direction is encouraging, but N=3 is far below a defensible performance sample. GBPUSD H2 remains a prospective-validation candidate, not a validated edge.

### USDJPY M1

Three independent 1,500-bar tick windows produced:

- offset 0: 7 trades, +0.3020R, expectancy +0.0431R;
- offset 1,500: 17 trades, +1.5658R, expectancy +0.0921R;
- offset 3,000: 11 trades, -0.9789R, expectancy -0.0890R.

Aggregate: 35 trades, +0.8890R, approximately +0.0254R/trade before commission/slippage. The signal is too thin to support promotion, but the sample is useful enough to retain USDJPY M1 for prospective validation.

### GBPJPY H4

A recent 120-bar window contained 5,617,662 accepted Bid/Ask ticks.

- OHLC model: 4 trades, +1.1104R, expectancy +0.2776R;
- observed-tick replay: 0 completed trades.

The discrepancy is material. A strategy that creates four completed operations under synthetic OHLC sequencing and none under the observed tick path cannot be promoted from the OHLC result. GBPJPY H4 remains non-promotable pending prospective evidence.

## Decision

The V111 fidelity port is real and deterministic; it is not dashboard-only text. It reacts to broker-server time, candles, Bid/Ask sequence, channel state, entries, partials, trailing logic and exits. The observed-tick tests demonstrate that changing the actual intrabar path changes its decisions and outcomes.

However, no tested combination currently satisfies a defensible profitability-promotion gate:

- XAUUSD M30: NO-GO for promotion after negative aggregate tick evidence;
- EURUSD H2: NO-GO for promotion on available tick evidence;
- GBPJPY H4: NO-GO for promotion because observed ticks fail to reproduce recent OHLC trades;
- USDJPY M1: HOLD for prospective validation; +0.0254R/trade before unmodelled costs is too thin;
- GBPUSD H2: HOLD for prospective validation; positive direction but only 3 tick-backed trades.

## Product/state transition

The Strategy Registry is advanced from `FIDELITY` to `VALIDATION` for the frozen V111 baseline. This is not a promotion to `SHADOW`, `EVENT_ELIGIBLE`, publication, or real execution.

The next legitimate evidence source is prospective market observation using the frozen V111 rules. Initial research scope is deliberately narrow:

1. GBPUSD H2 — insufficient tick N but positive observed direction;
2. USDJPY M1 — larger tick sample but thin residual expectancy.

These are validation probes, not recommendations. Every prospective occurrence must retain both successes and failures. No percentage win probability may be published until a sufficient, predeclared prospective sample exists.

## Remaining execution boundary

The observed-tick replay still models exact-level fills after seeing Bid/Ask quotes. It does not prove the broker would accept each V111 request at that level. Commission, swap and V111-specific slippage remain outside the read-only proof envelope.

Therefore the correct final classification on 2026-09-04 is:

**V111 PORT: FUNCTIONAL / VALIDATION READY.**

**V111 PROFIT EDGE: NOT VALIDATED.**

**REAL ORDER EXECUTION: FORBIDDEN.**

## Regression and safety evidence

Validation after the final code/state transition:

- Cycle Theory strategy suite: **144 passed**, 89 deselected, 0 failures;
- product/strategy/evidence registry directed suite: **24 passed**, 0 failures;
- full project regression: **543 passed, 1 expected skip, 0 failures**;
- Python compile/diff checks: PASS;
- frozen candidate hash self-check: TRUE;
- real-order call search in the validation scope: no `order_send`/Buy/Sell execution call found.

Raw screening/stability outputs remain local under `artifacts/` and are intentionally Git-ignored. This document is the canonical tracked decision record.

## Reproduction entry points

- single OHLC replay: `python -m backend.run_cycle_theory_replay`;
- broad screening: `python -m backend.run_cycle_theory_screening`;
- multi-window stability: `python -m backend.run_cycle_theory_stability`;
- observed Bid/Ask comparison: `python -m backend.run_cycle_theory_tick_replay`.
