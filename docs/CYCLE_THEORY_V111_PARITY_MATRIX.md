# Cycle Theory V111 — MQ5 ↔ HAGMARTK Parity Matrix

Audit date: 2026-08-29
Source of truth: `C:\Users\55819\Downloads\TEORIA_DOS_CICLOS ULTIMATE 1.mq5`
Python scope: `backend/strategies/cycle_theory/`
Status vocabulary: PROVEN / PARTIAL / MODELLED / OPEN.

## Gate policy

No optimization, performance claim, or production promotion is allowed until all execution-critical OPEN/MODELLED rows are either proven against MT5 evidence or explicitly bounded as research assumptions.

| Contract | MQ5 source | Python implementation | Status | Audit finding |
|---|---|---|---|---|
| OnTick ordering | 1783-1817 | `research_adapter.py::on_tick` | PROVEN | Control-flow order matches source: time gate → hard stop → active trade management → closure/capital/signal. |
| Lot normalization | 272-311 | `execution_model.py::calc_lot` | PROVEN | Fixed/auto-balance, volume step/min/max and BUY-side margin quirk preserved. |
| Margin calculation | 293 | `execution_model.py::_calc_margin_buy` | MODELLED | MQ5 uses broker `OrderCalcMargin`; Python uses fixed `margin_rate_per_lot`. Not broker-equivalent. |
| Market entry side | 1376-1410 | `execution_model.py` | PROVEN | BUY uses Ask; SELL uses Bid. |
| Limit submission | 1379/1410 | `execution_model.py` + `broker.py` | PROVEN | Submitted limit price/volume preserved by current broker model. |
| Pending fill trigger | MT5 engine | `tick_execution.py` | MODELLED | BUY_LIMIT Ask<=price; SELL_LIMIT Bid>=price. Needs real MT5 event parity evidence. |
| Spread gate | strategy entry functions | `signal_engine.py` | PARTIAL | Strategy checks spread; replay reconstructs Ask from historical/default spread. Historical spread quality remains data-dependent. |
| Stops/freeze validation | 412-441 | `position_manager.py::pode_modificar` | PROVEN | Minimum distance logic mirrors source. |
| Partial exits | 1200-1264 | `position_manager.py::manage_partials` | PROVEN | Ordering, one-time volume read and minimum-volume quirks intentionally preserved. |
| Final TP sync | 1051+ | `position_manager.py::sync_target_and_visuals` | PROVEN | Expansion target and smart buffer logic mirrored. |
| Breakeven/trailing | 1073+ | `position_manager.py::manage_trailing` | PARTIAL | Logic ported; fill/modify acceptance still depends on MockBroker rather than MT5 trade server. |
| Pullback cancellation | 1286-1356 | `research_adapter.py::check_pending_cancellation` | PROVEN | Ordering and magic-only pending lookup quirk preserved. |
| Trade closure reset delay | 1271-1281 | `research_adapter.py::check_trade_closure` | PROVEN | 3-second guard preserved, but replay timestamp granularity may affect equivalence. |
| Intrabar price path | MT5 real ticks | `historical_replay.py::_path` | MODELLED | Bull: O-L-H-C; Bear: O-H-L-C. Deterministic assumption can change event ordering. |
| SL/TP execution | MT5 trade engine | `tick_execution.py` | MODELLED | Trigger sides are correct, but exits execute exactly at SL/TP with no gap/slippage model. |
| Commission/swap | MT5 deal history | broker/ledger | OPEN | Structures exist, but replay performance is not yet proven to apply real commission/swap economics. |
| Slippage/gaps | MT5 execution | replay harness | OPEN | No broker slippage/gap-fill parity proven. |
| ATR | `iATR` | `historical_replay.py::_atr` | PARTIAL | Python uses simple TR average over replay window; exact MT5 iATR initialization/smoothing parity not yet proven. |
| Timezone/server time | `TimeCurrent`, `iTime` | replay datetime normalization | OPEN | Timezone-aware timestamps are stripped to naive; server-time parity must be demonstrated. |
| Terminal open PnL | live position state | replay mark-to-market | RESEARCH | Explicit research metric; not a synthetic realized trade. |
