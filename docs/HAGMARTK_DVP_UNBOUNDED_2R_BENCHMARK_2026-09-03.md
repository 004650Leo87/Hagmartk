# HAGMARTK DVP — Unbounded 2R Benchmark — 2026-09-03

## Scope

This audit replays only D+V+P events that also PASS the strict pre-reversal 2/2 Fibonacci research gate and that actually activated an entry.

The benchmark then follows each activated event from its recorded entry until either:

- structural stop is reached first;
- fixed +2R benchmark is reached first;
- both occur inside the same OHLC candle (ambiguous order);
- available market data ends before either event (censored).

There is no arbitrary 20-bar exit in this replay.

## Current MT5 cohort

- Activated four-confluence research events: 17
- +2R first: 5
- Stop first: 12
- Same-bar ambiguity: 0
- Censored at end of available data: 0
- Median bars to resolution: 20
- Maximum bars to resolution: 202
## Interpretation

The former 20-bar window was truncating many valid unresolved paths rather than expressing a strategy exit rule.

Nine events were still unresolved at 20 bars in the bounded audit. When observation is continued to the end of available data, all nine eventually resolve; some require substantially more than 20 bars.

The gross fixed-payoff benchmark for this cohort is mechanically 5 x +2R and 12 x -1R = -2R total, or approximately -0.118R per resolved event before costs. This is a HAGMARTK benchmark only and must not be presented as the performance of original DIVAP management.

No optimization decision may be made from this 17-event sample.

## Reproducibility

Run `python tools/research_dvp_unbounded_2r_replay.py` from the repository root while the scoped MT5 source is available.
