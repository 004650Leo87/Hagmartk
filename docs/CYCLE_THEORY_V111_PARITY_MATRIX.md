# Cycle Theory V111 — MQ5 ↔ HAGMARTK Parity Matrix

Audit date: 2026-08-29
Source of truth: `C:\Users\55819\Downloads\TEORIA_DOS_CICLOS ULTIMATE 1.mq5` (`#property version "111.00"`; description identifies V111)
Python scope: `backend/strategies/cycle_theory/`
Status vocabulary: PROVEN / PARTIAL / MODELLED / OPEN.

## Gate policy

No optimization, performance claim, or production promotion is allowed until all execution-critical OPEN/MODELLED rows are either proven against MT5 evidence or explicitly bounded as research assumptions.

| Contract | MQ5 source | Python implementation | Status | Audit finding |
|---|---|---|---|---|
| OnTick ordering | 1783-1817 | `research_adapter.py::on_tick` | PROVEN | Control-flow order matches source: time gate → hard stop → active trade management → closure/capital/signal. |
| Lot normalization | 272-311 | `execution_model.py::calc_lot` | PROVEN | Fixed/auto-balance, volume step/min/max and BUY-side margin quirk preserved. |
| Margin calculation | 293 | `execution_model.py::_calc_margin_buy` + `mt5_margin_evidence.py` | PROVEN | Gate 3N captured live calculation-only MT5 evidence via `order_calc_margin(ORDER_TYPE_BUY, EURUSD, 1.0, Ask)` with no `order_send`: Ask 1.15824 -> USD 231.65 margin on 1:500 account. Python model already honors explicit broker margin and preserves the BUY-side quirk. |
| Market entry side | 1376-1410 | `execution_model.py` | PROVEN | BUY uses Ask; SELL uses Bid. |
| Limit submission | 1379/1410 | `execution_model.py` + `broker.py` | PROVEN | Submitted limit price/volume preserved by current broker model. |
| Pending fill trigger | MT5 engine | `tick_execution.py` | MODELLED | BUY_LIMIT Ask<=price; SELL_LIMIT Bid>=price. Gate 3K additionally proves that the current research harness fills a gap-through limit at the submitted limit price. This is an explicit model contract, not MT5 parity; real tick/deal evidence is still required. |
| Spread gate | strategy entry functions | `signal_engine.py` | PROVEN | Gate 3N confirms source and Python use spread in integer symbol points with the same strict `> InpMaxSpread` gate, including the Expansion phase-1 quirk that does not gate spread until phase 2. Live MT5 evidence also confirmed `SYMBOL_SPREAD=4` equals `(Ask-Bid)/Point=4` on EURUSD. Historical replay spread quality remains a separate data-quality limitation, not a strategy-logic parity gap. |
| Stops/freeze validation | 412-441 | `position_manager.py::pode_modificar` | PROVEN | Minimum distance logic mirrors source. |
| Partial exits | 1200-1264 | `position_manager.py::manage_partials` | PROVEN | Ordering, one-time volume read and minimum-volume quirks intentionally preserved. |
| Final TP sync | 1051+ | `position_manager.py::sync_target_and_visuals` | PROVEN | Expansion target and smart buffer logic mirrored. |
| Breakeven/trailing | 1073+ | `position_manager.py::manage_trailing` | PARTIAL | Logic ported; fill/modify acceptance still depends on MockBroker rather than MT5 trade server. |
| Pullback cancellation | 1286-1356 | `research_adapter.py::check_pending_cancellation` | PROVEN | Ordering and magic-only pending lookup quirk preserved. |
| Trade closure reset delay | 1271-1281 | `research_adapter.py::check_trade_closure` | PROVEN | 3-second guard preserved, but replay timestamp granularity may affect equivalence. |
| Intrabar price path | MT5 real ticks | `historical_replay.py::_path` | MODELLED | Bull: O-L-H-C; Bear: O-H-L-C. Deterministic assumption can change event ordering. |
| SL/TP execution | MT5 trade engine | `tick_execution.py` | MODELLED | Trigger sides are correct. Gate 3M proves the current research harness executes a gap-through protective stop exactly at the submitted SL, not at the observed gap quote. This is an explicit idealized model contract, not MT5 parity; real tick/deal evidence is required before performance claims. |
| Commission/swap | 348-350 / MT5 deal history | broker/ledger | PARTIAL | Gate 3P adds read-only live broker evidence: 90-day MT5 history returned 69 exit-type deals; XAUUSD exit deals included non-zero commission and swap (61 exits: commission -1.83 USD, swap -0.54 USD in aggregate). This proves zero-cost replay is not economically faithful to the connected account. Replay remains explicitly ZERO_COMMISSION_ZERO_SWAP until a versioned cost model can be derived without contaminating strategy-specific results; therefore this row is not PROVEN. |
| Slippage/gaps | MT5 execution | replay harness | MODELLED | Gate 3I explicitly labels OHLC replay as idealized/no-slippage. Real broker gap/slippage parity remains unproven. |
| Deviation/filling policy | OnInit: SetDeviationInPoints(InpDeviation) + SetTypeFilling(...) | replay/mock execution | PARTIAL | Gate 3O corrects the earlier audit assumption: V111 explicitly sets InpDeviation=100 points and selects FOK first, then IOC, else RETURN from SYMBOL_FILLING_MODE. Official MQL5 docs confirm deviation is the allowed deviation in points and filling type configures the order policy. Live read-only MT5 evidence on the connected terminal reported filling_mode=2 for EURUSD/XAUUSD. The replay does not model broker acceptance, partial-fill/reject/requote behavior or deviation-bounded execution, so economic execution parity remains unproven. |
| ATR | `iATR` | `historical_replay.py::_atr` | PARTIAL | Gate 3F removed intrabar future-high/low leakage and ATR now evolves with revealed path. Exact MT5 indicator parity still needs terminal evidence. |
| Current-bar OHLC visibility | `iHigh/iLow/iClose` on forming bar | `historical_replay.py` progressive partial bar | PROVEN | Replay publishes only high/low/close observed up to each synthetic tick; adversarial Gate 3J test prevents final-bar look-ahead. |
| Timezone/server time | `TimeCurrent`, `iTime` | replay datetime normalization | PARTIAL | Gate 3Q adds read-only live terminal evidence from Tickmill-Live: MT5 Python tick/bar epochs were captured as UTC for EURUSD/XAUUSD, consistent with the generic market adapter contract. This does NOT reveal the MQL5 `TimeCurrent()` broker-server wall clock offset/DST mapping. Gate 3G therefore remains valid: replay must not relabel UTC as naive server time, and explicit UTC-to-server conversion still requires direct broker/MQL5 evidence. |
| Terminal open PnL | live position state | replay mark-to-market | RESEARCH | Explicit research metric; not a synthetic realized trade. |

| Warmup execution semantics | EA starts evaluating immediately after OnInit; indicator availability is terminal-managed | replay preloads history and intentionally suppresses strategy ticks during configured warmup | MODELLED | Gate 3L proves current replay behavior. V111 has no explicit warmup gate or BarsCalculated guard; the CLI-derived max(5, ATR period) remains a research harness assumption, not source parity. |
