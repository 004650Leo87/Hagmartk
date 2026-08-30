# Cycle Theory V111 — Gate 3AA Tick Time-Domain Guard

**Date:** 2026-08-30
**Status:** SAFETY CONTRACT / SERVER-TIME PARITY STILL PARTIAL

The tick-backed replay removes the synthetic OHLC path assumption, but real MT5 Python ticks are UTC epochs while V111 uses broker-server wall clock through `TimeCurrent()` / `iTime()`.

To prevent silent time-domain corruption, `CycleTheoryTickHistoricalReplay` now rejects timezone-aware tick/bar timestamps until an explicit UTC-to-broker-server mapping is evidenced. It also rejects inverted Bid/Ask ticks.

This does not solve broker-server offset/DST parity. It prevents the higher-fidelity tick path from falsely implying time fidelity that has not been proven.

No live order or server modification is used by this gate.
