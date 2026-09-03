# HAGMARTK DVP — Higher-Timeframe Fibonacci Context Gate — 2026-09-03

Status: RESEARCH / NOT PROMOTED

## Source-backed boundary

Fernando Pereira's public DIVAP lesson provides a concrete cross-timeframe example around 13:23:

- targets from a 4-hour operation are carried into a 15-minute chart;
- price reaches the higher-timeframe Fibonacci target area;
- a bearish reversal pattern is then identified on the lower timeframe;
- the lower-timeframe short is structured below the reversal-pattern low with stop above its high.

This supports **H4 target -> M15 reversal context** as a source-described construction example.

It does not establish a universal mapping among every timeframe pair, nor a unique automatic parent-trade/anchor selector.

## First bounded automation hypothesis

Policy ID: `HTF_TARGET_CONTEXT_H4_TO_M15_V1`.

Only H4 -> M15 is tested. No extrapolation to M5/M30/H1/H2/D1/W1 is permitted in this gate.

Research contract:

1. The parent must be an activated H4 `HDF_DVP` occurrence that also passed the existing strict pre-reversal Fibonacci research gate.
2. Parent target levels are produced by the already-bounded `POST_REVERSAL_PATTERN_RANGE_V1`; this remains HAGMARTK-authored target automation, not claimed as the source's unique H4 drawing.
3. The M15 child must independently satisfy divergence + volume + reversal-pattern (`HDF_DVP`) before higher-timeframe Fibonacci is considered.
4. Parent direction must be opposite the M15 reversal direction, matching the source-demonstrated use case.
5. The H4 target level must be known before the M15 decision candle.
6. The parent activation must fall inside the frozen M15 snapshot so prior level contact and stop state are observable at M15 resolution.
7. The selected H4 target must have no earlier M15 contact after parent activation.
8. The parent structural stop must not have occurred before the child decision.
9. Same-bar parent-target/parent-stop ambiguity at the child candle is reported, not resolved optimistically.

## Interpretation boundary

This is a fidelity/causality test. It does not measure profitability and cannot promote a production rule from sparse matches alone.

## First-touch same-bar sub-hypothesis result

An aligned H4/M15 snapshot was captured using 1,200 H4 bars per symbol and the complete M15 history inside each symbol's exact H4 UTC range.

- Snapshot rows: **262,784**.
- Qualified H4 parents under the current strict pre-reversal research gate: **2**.
- M15 divergence + volume + pattern occurrences: **400**.
- Exact first-target-touch on the M15 reversal decision bar: **0**.

This **does not reject higher-timeframe context**. The source-demonstrated sequence shows the higher-timeframe target being reached before the lower-timeframe reversal is discussed. Therefore the same-bar/first-touch restriction was more stringent than the source example and is not promoted.

The aligned snapshot is retained and reused by default; a new capture requires `--refresh`.

## Next diagnostic frozen before execution

For each qualified H4 parent target, determine target-first vs stop-first at M15 resolution. If target is reached first, measure the lag in M15 bars to the **earliest subsequent opposite-direction M15 DVP reversal**. No maximum lag threshold is imposed or optimized in this diagnostic.

## Lag diagnostic result

On the aligned frozen snapshot:

- H4 target levels evaluated from the 2 qualified parents: **10**.
- Target reached before parent stop: **5**.
- Parent stop before target: **5**.
- Each of the 5 target-first levels had a later opposite-direction M15 DVP occurrence.

However, the earliest subsequent opposite M15 reversal occurred very late:

- minimum lag: **314 M15 bars**;
- first quartile: **350 bars**;
- median: **897 bars**;
- third quartile: **1,055 bars**;
- maximum: **1,073 bars**.

At those earliest reversals, distance from the H4 target to the M15 decision-candle range was **0.103R to 1.431R** of the parent H4 risk, median **0.485R**.

## Decision

`HTF_TARGET_CONTEXT_H4_TO_M15_V1` remains **INSUFFICIENT / NOT PROMOTED**.

Reasons:

1. The source concept is real, but the inspected public material provides an example rather than a universal machine-selection rule.
2. The frozen sample contains only **2** H4 parents after the current strict Fibonacci research gate, both bearish; it does not reproduce the same parent/child polarity demonstrated in the source example.
3. No exact first-touch M15 reversal was found.
4. After genuine H4 target-first events, the earliest opposite M15 DVP reversals were hundreds of M15 bars later and no longer tightly located at the H4 target.
5. Choosing a maximum lag now from these outcomes would be retrospective optimization and is prohibited.

No timeframe mapping, context-age threshold or HTF Fibonacci rule is added to the HDF engine.

Reproduction:

- `python tools/research_dvp_htf_fibonacci_context.py`
- `python tools/research_dvp_htf_context_lag_diagnostic.py`
