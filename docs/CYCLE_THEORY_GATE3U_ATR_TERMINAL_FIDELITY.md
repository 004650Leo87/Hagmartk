# Cycle Theory V111 — Gate 3U ATR Terminal Fidelity

**Date:** 2026-08-30
**Status:** SOURCE-PROVEN ALGORITHM / TERMINAL AVAILABILITY BOUNDED

## Evidence source
The installed MetaTrader 5 standard indicator source was inspected at:
`MQL5/Indicators/Examples/ATR.mq5` (MetaQuotes Ltd., Copyright 2000-2024).

The source computes True Range as `max(high, previous close) - min(low, previous close)` and initializes the first ATR only when `rates_total > period`. The first ATR is the average of TR values 1..period; subsequent values use the rolling SMA recurrence.

## Divergence found
HAGMARTK `_atr()` previously returned a non-zero ATR as soon as two bars existed. That could expose an ATR value before the MetaTrader indicator has enough bars, especially when replay warmup is reduced or disabled.

## Correction
`historical_replay.py::_atr` now returns zero until `len(bars) > period`, then averages exactly the latest `period` True Range observations. Adversarial tests freeze the first-valid-bar boundary and rolling calculation.

## Remaining limitation
V111 obtains ATR through `CopyBuffer(handleATR, 0, 0, 1, atr)` on the current/forming bar. HAGMARTK now mirrors the documented/installed calculation and progressive current-bar visibility, but a direct live `CopyBuffer` value from the EA has not yet been captured through Python. Therefore algorithmic parity is PROVEN while live handle/availability parity remains PARTIAL.

## Product consequence
ATR calculation itself no longer needs to be treated as an unknown formula. Remaining ATR risk is terminal indicator availability/timing, not the rolling True Range arithmetic.
