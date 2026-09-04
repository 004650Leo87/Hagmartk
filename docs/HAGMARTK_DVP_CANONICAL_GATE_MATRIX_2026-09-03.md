# HAGMARTK DVP — Canonical Gate Matrix — 2026-09-03

Status: ACTIVE RESEARCH / PROSPECTIVE COLLECTION

This document is the canonical boundary for the current DVP workstream. It prevents reopening frozen decisions merely because no new live DVP event has appeared yet.

## Source-backed core — CLOSED

| Component | Status | Canonical rule |
|---|---|---|
| RSI/IFR | CLOSED | Wilder RSI/IFR 14 in the current contract. |
| Divergence Level 1 | CLOSED | Regular geometric divergence at confirmed price pivots; no invented absolute RSI 30/70 admission gate. |
| Volume | CLOSED | Volume above its 20-period average. |
| Reversal | CLOSED | Graphical/candlestick reversal; demonstrated patterns include hammer, shooting star and engulfing. |
| Buy activation | CLOSED | Above reversal-pattern high. |
| Sell activation | CLOSED | Below reversal-pattern low. |
| Structural stop | CLOSED | Opposite side of the reversal pattern. |
| Markets/timeframes | CLOSED BOUNDARY | Method is described across markets/timeframes; H1/H4/D1 are described as more effective, not exclusive. |

## Fibonacci construction — RESEARCH ONLY

| Policy / question | Status | Boundary |
|---|---|---|
| Fibonacci levels 61.8/100/161.8/200/261.8 | SOURCE-BACKED | Mathematics/levels are source-described. |
| `PRE_REVERSAL_STRICT_V1` | RESEARCH-ONLY / PROSPECTIVE | Deterministic HAGMARTK selector: latest valid confirmed leg strictly before reversal P2. It must not be claimed as the unique original DIVAP auto-anchor rule. |
| `POST_REVERSAL_PATTERN_RANGE_V1` | RESEARCH-ONLY / PROSPECTIVE | Deterministic HAGMARTK target construction using the reversal-pattern range known at decision time. |
| Fib200 = 2R | CONDITIONAL IDENTITY / NOT PROMOTED | Exact only under the current zero-gap, zero-buffer geometry; provenance remains separate. |
| H4 -> M15 target context | INSUFFICIENT / NOT PROMOTED | Source example exists, but current aligned replay does not support a deterministic general rule. |
| Universal swing selector | UNRESOLVED | Public source does not freeze one unique forward-knowable automatic selector. |

## Exit management — FROZEN BOUNDARY

- `EXIT_2R` is the frozen HAGMARTK quantitative benchmark of candidate `hdf_dvp_exit_2r` v1.0.0.
- `EXIT_2R` is not an original DIVAP claim.
- Public DIVAP material supports Fibonacci target zones and discretionary partial realization, but does not freeze universal percentages, mandatory full-exit target, stop movement, or a time-based forced exit.
- The 20-bar concept remains telemetry/research horizon only; it is not an exit rule.
- Unresolved positions at arbitrary horizons remain open/censored.

## Prospective evidence state at checkpoint

- Shadow T0 after MT5 clock-integrity reset: `2026-09-04 01:40:49 UTC`.
- Fibonacci research T0: `2026-09-04 01:27:59 UTC`; effective Fibonacci gate uses the stricter applicable T0.
- Scanner universe: 39 combinations (13 assets x M15/H1/H4).
- Scanner coverage at checkpoint: 285 expected / 285 successful / 0 failed = 100% HEALTHY.
- Live HDF evidence: 1 (`USDCHF`, M15, BEARISH, `HDF_DV`, detected 2026-09-04T01:45:00Z).
- Live complete DVP/Fibonacci telemetry records: 0.
- Fibonacci maturity: INSUFFICIENT; automatic promotion is forbidden.

## Allowed next actions

1. Continue prospective collection without changing candidate parameters.
2. Record every future Fibonacci decision snapshot immutably and evaluate outcomes only after the decision.
3. Re-evaluate research modes only when the frozen sample thresholds are reached or a materially new primary source changes the source contract.
4. Keep source-backed core rules closed unless contradictory primary evidence is found.
5. Do not tune swing selection, lag windows, target allocation or exit rules from realized outcomes.

## Explicitly prohibited rework

No new historical optimization should be started merely because the live Fibonacci sample is still zero. A lack of live events is a valid observation, not a reason to loosen the four-confluence gate.
