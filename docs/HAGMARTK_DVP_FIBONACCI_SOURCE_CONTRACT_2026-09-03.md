# HAGMARTK DVP ? Fibonacci Source Contract ? 2026-09-03

Status: RESEARCH / NOT PROMOTED

## Source-backed facts
- DIVAP requires price to arrive at an extension target: 61.8, 100, 161.8, 200 or 261.8.
- Fernando's public lesson explicitly describes using the minimum and maximum before reversal to trace targets.
- The same lesson also allows pre-reversal, post-reversal, or a shorter movement as valid tracing constructions.
- A later example explicitly analyses minimum and maximum after reversal.
- Higher-timeframe targets may serve as Fibonacci context for lower-timeframe trades (example H4 -> M15).

## Engineering consequence
There is no evidence that a single universal swing pair represents every valid DIVAP Fibonacci construction. Therefore HAGMARTK must not retrospectively search all swing pairs and accept whichever touches a source level.

Each construction mode must have its own deterministic, forward-knowable anchor-selection policy and provenance. The policy must be fixed before evaluating the target contact.

## First policy to test
PRE_REVERSAL_LATEST_CONFIRMED_LEG_V1: at the decision time, use only confirmed pivots; choose the latest completed directional leg before the reversal/confluence. No future pivot and no best-fit search are permitted.

This is a HAGMARTK automation hypothesis derived from the source construction, not claimed as Fernando Pereira's unique automatic algorithm.
