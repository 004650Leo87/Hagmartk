# Cycle Theory V111 — Gate 3Y Restart/Persistence Quirk

**Date:** 2026-08-30
**Status:** SOURCE-PROVEN QUIRK

## Source behavior
V111 persists exactly seven channel fields through `SaveMemory()` and reads them only through `LoadMemory()`. Source search shows `LoadMemory()` is called only inside `ManageTrailing()` when `superSize <= _Point`.

On the first tick with an active trade after a fresh runtime, `currentState != STATE_TRADING`, so V111 sets `STATE_TRADING` and calls `SaveMemory()` **before** `ManageTrailing()`. Because the runtime channel fields start empty, this can overwrite previously stored GlobalVariables before the later `LoadMemory()` attempt.

There is no `LoadMemory()` call in `OnInit()` and no automatic restore path when there is no active trade.

## HAGMARTK parity
The research adapter preserves the same ordering: active-trade detection -> state promotion -> `save_memory` -> trailing -> conditional `load_memory`. An adversarial restart test preloads channel state, simulates a fresh runtime with an active position, and proves the stored channel is overwritten with zeroed runtime state before load.

## Interpretation
This is not a reliability feature; it is a source quirk. HAGMARTK must preserve it during fidelity research rather than silently repair the strategy. Any future production hardening that changes restart recovery must be a new strategy/runtime version with explicit evidence, not a hidden parity fix.
