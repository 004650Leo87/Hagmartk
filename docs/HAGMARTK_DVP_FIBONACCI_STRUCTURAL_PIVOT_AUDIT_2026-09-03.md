# HAGMARTK DVP - Fibonacci Structural Pivot Audit

Date: 2026-09-03
Status: RESEARCH ONLY / NOT PROMOTED

## Hypothesis frozen before comparison

Compare the current strict pre-reversal Fibonacci policy using two pivot granularities only:

- `MICRO_2_2`: current pivot definition, 2 candles left + 2 right.
- `STRUCTURAL_5_5`: experimental structural comparator, 5 candles left + 5 right.

Both policies must use only pivots confirmed by decision time and both Fibonacci anchors must be strictly before divergence pivot P2. No later Fibonacci contact is used to choose the pivot window.

## Current live cohort

13 assets x 6 timeframes (M5, M15, M30, H1, H2, H4), 1200 candles requested per combination.
Current rolling MT5 cohort produced 134 HDF_DVP occurrences. The immediately previous audit had 135; this document does not pretend they are identical cohorts.
## Results

- `MICRO_2_2`: 22 PASS / 112 FAIL = 16.42% PASS.
- `STRUCTURAL_5_5`: 14 PASS / 120 FAIL = 10.45% PASS.
- Overlap: 10 PASS in both policies.
- 12 events PASS only under `MICRO_2_2`.
- 4 events PASS only under `STRUCTURAL_5_5`.

By timeframe, structural PASS counts were M5=4, M15=1, M30=5, H1=1, H2=1, H4=2.

## Interpretation boundary

This does not prove `MICRO_2_2` is the original DIVAP anchor algorithm and does not measure profitability. It shows that widening the pivot-confirmation hierarchy materially changes which events satisfy Fibonacci, while remaining causal.

Because the public source does not specify a deterministic pivot-width hierarchy, neither window is promoted as source truth. The simpler current 2/2 policy remains the leading HAGMARTK automation hypothesis until stronger source evidence or prospective validation justifies a hierarchy change.

Reproduction: `python tools/research_dvp_fibonacci_pivot_hierarchy.py`.