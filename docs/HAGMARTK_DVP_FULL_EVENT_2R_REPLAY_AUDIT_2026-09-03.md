# HAGMARTK DVP ? Full Event 2R Replay Audit ? 2026-09-03

## Scope
Research-only audit of activated D+V+P candidates that also PASS strict pre-reversal Fibonacci 2/2.
No strategy parameter was promoted or changed.

## Cohort
Current rolling MT5 sample: 13 assets x 6 timeframes x 1200 candles.
22 candidates PASS strict pre-reversal Fibonacci; 17 activated; 5 never activated.

## Replay contract
Start at activation bar. Use recorded entry and initial structural stop. Target = exactly 2R.
Evaluate at most 20 bars, matching the current realizable-excursion horizon.
If stop and 2R occur in same OHLC bar, mark AMBIGUOUS_SAME_BAR; never infer intrabar order.
If neither occurs in 20 bars, mark OPEN_20.

## Result
- 2R_FIRST: 3
- STOP_FIRST: 5
- OPEN_20: 9
- AMBIGUOUS_SAME_BAR: 0

This is not a 3/8 win-rate claim for the strategy. Nine activated events remain unresolved under the 20-bar replay contract.
The earlier ad-hoc 5/12 classification is rejected because it used an unbounded future window while comparing against 20-bar MFE/MAE fields.

## Integrity finding
`mfe_r` is raw 20-bar excursion and may include movement after a stop. `metadata.realizable_mfe_r` stops at the first structural stop.
Therefore raw MFE must not be used as realized EXIT_2R evidence.

## Decision
Keep Fibonacci and full-event policy in RESEARCH_ONLY. No performance promotion.
Next gate: define the lifecycle after 20 bars and/or replay the frozen EXIT_2R contract on a sufficiently bounded historical/prospective event ledger without changing rules after outcomes are known.
