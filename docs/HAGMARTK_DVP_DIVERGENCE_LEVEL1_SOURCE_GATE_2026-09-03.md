# HAGMARTK DVP — Divergence Level 1 Source Gate — 2026-09-03

Status: SOURCE-BACKED / NO RSI 30-70 GATE

## Source conclusion
The Fernando Pereira DIVAP video states that three divergence levels exist and that Level 1 is the one used because it is the most effective in the method.
The public technical-analysis PDF defines the DIVAP divergence geometrically:
- bearish: higher price highs with lower IFR/RSI highs;
- bullish: lower price lows with higher IFR/RSI lows.

Neither inspected source makes RSI >= 70 or RSI <= 30 a mandatory DIVAP Level-1 admission condition.
Therefore HAGMARTK must not invent an absolute 30/70 filter.

## Empirical integrity audit
A live MT5 audit covered 13 symbols across M5/M15/M30/H1/H2/H4 and inspected 135 HDF_DVP occurrences.
Stored RSI values matched RSI recomputed at the exact price-pivot candle in all 135 occurrences: 0 mismatches.
Some valid geometric divergences had bullish RSI2 > 70 or bearish RSI2 < 30; those observations are retained, not silently filtered.

## Frozen research interpretation
Level 1 = regular geometric divergence at confirmed price pivots, using RSI/IFR 14 at those pivot candles.
30/70 remains descriptive evidence (`rsi_extreme_class`), not an eligibility gate.
Pivot confirmation remains forward-knowable; RSI belongs to pivot time, not confirmation time.

Next gate: return to Fibonacci swing-selection fidelity without changing this divergence contract unless stronger primary-source evidence contradicts it.
