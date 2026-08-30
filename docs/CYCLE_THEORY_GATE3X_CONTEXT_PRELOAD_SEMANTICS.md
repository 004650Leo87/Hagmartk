# Cycle Theory V111 — Gate 3X Context Preload Semantics

**Date:** 2026-08-30
**Status:** FRESH-START SEMANTICS BOUNDED

## Finding
The replay `warmup_bars` are better interpreted as **pre-existing terminal history before EA evaluation begins**, not as candles the running EA deliberately ignores. `power_on()` does not consume market bars; warmup bars are published into broker history without calling strategy `on_tick`, and the first evaluated candle then behaves like the EA's first live tick after startup.

V111 itself sets `refTimeStart = iTime(...,0)` on its first strategy tick and then waits until `iBarShift(refTimeStart) >= 5` before defining the channel from the four closed candles immediately after that reference. Historical bars before startup are context, not prior strategy execution.

## Default context
The CLI default remains `max(5, atr_period)` = 14 bars. After Gate 3U, the first evaluated candle therefore sees 15 bars (14 pre-existing + current forming), exactly enough for the standard ATR(14) first valid value. An adversarial test freezes this boundary.

## Remaining limitation
This does not prove restart fidelity when V111 restores persisted memory or discovers an already-active position. HAGMARTK's research `power_on()` resets the cycle and does not reproduce every live terminal restart state. Therefore warmup/context status advances from MODELLED to PARTIAL, not PROVEN.
