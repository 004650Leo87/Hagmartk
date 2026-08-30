# Cycle Theory V111 — Gate 3T Live Tick Path Evidence

**Date:** 2026-08-30
**Status:** READ-ONLY EVIDENCE / NO ORDER EXECUTION

## Purpose
Quantify whether the deterministic historical replay path (`bull: O-L-H-C`, `bear: O-H-L-C`) reproduces the observed order of candle extremes in real MT5 ticks.

## Method
- Source: connected MT5 terminal, Tickmill-Live.
- Symbols: EURUSD and XAUUSD.
- Timeframe: M1.
- Sample: 120 recent closed bars per symbol.
- Tick source: `copy_ticks_range(..., COPY_TICKS_INFO)`.
- Comparison: which Bid extreme, candle HIGH or LOW, was first reached by observed ticks.
- Safety: no `order_send`, no position/order mutation.

## Result
| Symbol | Bars | Resolved | Model matches | Mismatches | Match rate | Ticks |
|---|---:|---:|---:|---:|---:|---:|
| EURUSD | 120 | 119 | 99 | 20 | 83.19% | 5,029 |
| XAUUSD | 120 | 120 | 109 | 11 | 90.83% | 23,629 |

## Interpretation
The deterministic OHLC path is useful as a reproducible research model, but the observed tick order disproves treating it as execution truth. A mismatch can change which trigger, pending fill, stop, target, partial or trailing action occurs first inside the same candle.

This sample does **not** estimate strategy profitability and does not claim the mismatch rates are stable across sessions, regimes, symbols or timeframes. It only establishes that real tick ordering can differ materially from the deterministic path.

## Product consequence
Execution-grade validation of Cycle Theory V111 must use a tick-backed replay path, or keep intrabar execution explicitly MODELLED. OHLC-only results cannot be promoted as broker-faithful net performance.

## Reproducibility
Evidence harness: `backend/strategies/cycle_theory/mt5_tick_path_evidence.py`.
Pure tests: `tests/strategies/test_cycle_theory_tick_path_evidence.py`.
A tick-backed research engine now consumes chronological Bid/Ask ticks with observed spread, so intrabar path status advances to PARTIAL. It is not PROVEN because exact broker-server time mapping and broker-side fill acceptance/slippage remain unresolved.
