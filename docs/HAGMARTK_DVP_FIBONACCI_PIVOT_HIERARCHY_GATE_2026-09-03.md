# HAGMARTK DVP — Fibonacci Pivot Hierarchy Gate — 2026-09-03

## Source evidence
Fernando Pereira's public DIVAP lesson states that Fibonacci extension targets are built from the minimum and maximum before reversal, while also acknowledging pre-reversal, post-reversal and shorter constructions.

A separate public lesson on candlestick/Fibonacci gives an important structural example: a hammer can be treated as a very small bullish pivot; on a lower timeframe the same candle becomes an explicit up-leg, pullback and break of the prior high. The extension is projected from the minimum to the maximum of that movement.

This supports a pivot/leg interpretation. It does not support selecting an anchor merely because it is the largest price range or the longest elapsed interval in an arbitrary historical window.

## HAGMARTK boundary
The automatic anchor policy must remain causal and structural. It must not search multiple historical legs and accept whichever one makes the decision candle touch a Fibonacci level.

Current research candidate remains `STRICT_PRE_REVERSAL_LATEST_CONFIRMED_LEG`: use only pivots confirmed by decision time, require both anchors before P2/reversal, and select the latest valid directional leg.

## Prospective comparison already observed
On the same 135 real D+V+P occurrences (13 assets × M5/M15/M30/H1/H2/H4, 1200 candles):
- latest strict pre-reversal leg: 22 PASS / 135;
- largest price-amplitude eligible leg: 8 PASS / 135;
- longest-duration eligible leg: 13 PASS / 135.

These rates are fidelity diagnostics, not performance metrics. The latest-leg policy is not selected because it has the highest PASS count; it remains the lead hypothesis because its selection rule is simpler, forward-knowable and closer to the source's pivot/leg language.

## Unresolved fidelity question
Public material inspected so far does not provide a deterministic algorithm for choosing between a structural pivot and nested micro-pivots when both exist before the reversal. Therefore no hierarchy rule is promoted as original DIVAP truth.

Next gate: test an explicit, predeclared structural-significance rule without using Fibonacci contact as the selector. Until that gate passes, Fibonacci remains research-only and cannot promote HAGMARTK DVP to four-confluence confirmed status.
