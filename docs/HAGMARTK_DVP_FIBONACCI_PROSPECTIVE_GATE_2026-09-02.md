# HAGMARTK DVP — Fibonacci Prospective Gate — 2026-09-02

Status: RESEARCH / NOT PROMOTED

## Objective
Test the deterministic `latest completed leg` Fibonacci hypothesis against real MT5 candles without changing frozen HDF V1.

## Runtime evidence
Source: scoped HAGMARTK MF MT5 adapter, Pepperstone Group Limited binary, build 6140.
Sample: latest 1,500 candles per selected symbol/timeframe.
No orders were sent.

## Method
1. Run existing HDF_DVP detector.
2. At each confluence decision candle, expose only pivots already confirmed at that index.
3. Select one latest completed opposite-to-direction leg.
4. Project 61.8%, 100%, 161.8%, 200%, 261.8%.
5. PASS only when a projected level lies inside the real decision-candle high/low range.
6. No arbitrary price tolerance and no retrospective search for a better anchor pair.

## Observed result
Existing HDF_DVP occurrences in the fetched windows: 14.
Fibonacci PASS under this research policy: 1.
Fibonacci FAIL: 13.
Observed PASS: USDCHF M15 bullish, decision 2026-08-28 17:30 UTC, 200% level.

Breakdown:
- EURJPY H1: 3 HDF_DVP, 0 Fibonacci PASS.
- AUDUSD H1: 4 HDF_DVP, 0 PASS.
- ETHUSD M15: 0 HDF_DVP in current 1,500-bar window.
- XAGUSD M15: 3 HDF_DVP, 0 PASS.
- USDCHF M15: 4 HDF_DVP, 1 PASS.
- GBPUSD M15: 0 HDF_DVP in current 1,500-bar window.

## Decision
Do NOT promote this Fibonacci anchor policy yet.
The 1/14 pass rate is useful discrimination evidence, not proof of fidelity to Fernando Pereira's original anchor-selection rule.
Keep `fib_policy_promoted=False`; complete HAGMARTK DVP emission remains blocked.
Next validation should compare source-demonstrated chart examples against the exact anchor pair selected prospectively.
