# Cycle Theory V111 — Gate 3AC Read-Only MQL5 Probe

**Date:** 2026-09-02
**Status:** PROBE COMPILED / EXECUTION EVIDENCE PENDING

A dedicated MQL5 script was created to observe terminal-managed facts without any trading operation:
`tools/mql5/HAGMARTK_FIDELITY_PROBE.mq5`.

The probe records `TimeCurrent()`, `TimeTradeServer()`, `iTime(...,0)`, current tick epoch/Bid/Ask, `Bars`, `BarsCalculated`, and the result/value/error of `CopyBuffer(iATR(...),0,0,1)`.

Safety boundary: the source contains no CTrade, OrderSend, PositionModify, cancellation, order creation, or account mutation. It only reads terminal state and writes one CSV row to the terminal Files sandbox.

MetaEditor command-line compilation was validated against the active MT5 data directory. Result: **0 errors, 0 warnings**; EX5 generated successfully.

## Evidence boundary
Compilation proves syntax/build viability only. It does **not** prove live `CopyBuffer` availability or broker-server time mapping. Those rows remain PARTIAL until the compiled script is actually executed on a live chart and its CSV evidence is captured.

## Execution attempt 2026-09-02
The probe compiled in the Pepperstone MetaEditor with 0 errors and 0 warnings. A guarded startup attempt used AllowLiveTrading=0 and AllowDllImport=0, but no probe CSV or terminal execution evidence was produced. Therefore ATR CopyBuffer timing and broker-server time remain PARTIAL. The running Tickmill terminal had 0 positions and 0 orders at inspection. No trade action was performed. Multiple MT5 terminal installations are present, so further automation must not restart or mutate the active terminal merely to force the probe.
