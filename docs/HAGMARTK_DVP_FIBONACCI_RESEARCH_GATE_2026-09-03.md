# HAGMARTK DVP ? Fibonacci Research Gate ? 2026-09-03

## Decision
The frozen `hdf_dvp_exit_2r` v1.0.0 candidate is unchanged. Its historical `HDF_DVP` label means divergence + relative-volume + reversal-pattern evidence, not a complete Fibonacci-gated HAGMARTK DVP event.

## Public-method evidence recovered
Fernando Pereira/Horistic publicly describes the original setup as four technical components: RSI divergence, volume, Fibonacci extension target and reversal pattern. Public material specifies RSI 14, volume above a 20-period average, Fibonacci extension targets 61.8%, 100%, 161.8%, 200% or 261.8%, and reversal-pattern confirmation.

The public video also describes trend-based Fibonacci extension using a minimum/maximum movement and repeating the terminal endpoint for projection. It also explicitly presents more than one valid way to choose the market extrema used for the extension. Therefore the projection mathematics can be implemented deterministically, while automatic anchor selection is not yet uniquely specified.

## Implemented research primitive
`backend/strategies/hdf/fibonacci_audit.py` implements only the source-bounded projection mathematics and an explicit-anchor audit. It never selects market pivots automatically. Supported source levels are 0.618, 1.0, 1.618, 2.0 and 2.618.

A Fibonacci gate cannot return product-level PASS until the anchor-selection policy is uniquely versioned and validated. No tolerance band is invented. Historical research counts a contact only when a projected level lies inside the real high-low range of the confluence candle.

## Six historical HDF_DVP records
Research enumeration used only adjacent alternating confirmed pivots available before the decision candle, limited to recent structure. This is an ambiguity test, not a production anchor-selection algorithm.

- GBPUSD M15: 0 Fibonacci contacts.
- USDCHF M15: 0 Fibonacci contacts.
- XAGUSD M15: 6 possible contacts.
- ETHUSD M15: 8 possible contacts.
- AUDUSD H1: 6 possible contacts.
- EURJPY H1: 2 possible contacts.

## Interpretation
Zero contacts means the historical HDF_DVP cannot satisfy the researched Fibonacci gate under this bounded audit. Multiple contacts mean the event is ambiguous because several prior pivot pairs can retrospectively explain the same confluence candle. Ambiguity must never be silently resolved by choosing the pair that best fits after the fact.

## Next gate
Recover or validate a unique, forward-knowable anchor-selection rule from source examples. Then freeze it as a versioned HAGMARTK policy, add bullish/bearish fixture tests, and rerun the six historical records. Only events passing divergence + RSI + volume + Fibonacci + pattern under that frozen policy may receive the complete HAGMARTK DVP classification.
