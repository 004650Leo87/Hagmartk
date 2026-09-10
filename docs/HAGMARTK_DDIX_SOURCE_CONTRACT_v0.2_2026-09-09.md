# HAGMARTK DDIX v0.2 — Source Contract

Date: 2026-09-09
Status: RESEARCH CONTRACT — NOT AN OPERATIONAL CANDIDATE
Project: HAGMARTK SHADOW
Display name: **HAGMARTK DDIX**

## 1. Purpose

This document freezes only what is sufficiently supported by identifiable sources about the Didi Index / Agulhadas system attributed to Didi Aguiar.

It is a research contract, not a trading rulebook yet. No Telegram publication, PAPER execution, scoring, optimization or real-order path may be enabled from this document alone.

Mandatory stage gate:

1. source evidence;
2. explicit hypotheses;
3. deterministic implementation;
4. visual/reference parity tests;
5. historical replay;
6. prospective Shadow validation;
7. only then publication policy.

## 2. Source authority hierarchy

**Tier A — direct/official Didi ecosystem.** Didi's current official site and pages where Didi is the named instructor. Highest authority for authorship, scope and component list.

**Tier B — direct interviews with Didi.** Useful for origin, intent, terminology and qualitative rules stated by Didi himself.
**Tier C — official platform/vendor documentation.** Nelogica documents its Didi Index implementation and parameters. This is strong implementation evidence, but does not override a direct rule from Didi.

**Tier D — archival/educational reproductions.** Clear educational material and circulating course/apostila copies. Useful for parameter candidates and detailed trade-system rules, but require parity against stronger sources before freezing.

**Tier E — community implementations.** TradingView, MQL5, blogs and user code. Useful only to generate testable hypotheses; never authoritative by themselves.

## 3. High-confidence source registry

### A1 — Didi official/current ecosystem
- https://didiaguiar.com/cst-2026
- https://didiaguiar.com/go-c
- https://grafiques.didiaguiar.com/

These sources identify Didi Aguiar as creator of the Didi Index / Agulhada and place it inside his broader method.

### A2 — Course with Didi as named instructor
- https://elearning.showmethemoneytv.com/curso/curso-completo/

The course curriculum explicitly separates: DMI, Didi Index, Estocástico, TRIX, Bollinger, Análise Técnica, Candlestick and Indexação.

This is enough to freeze that the complete DDIX research model must not be reduced to the 3/8/20 crossing alone.

### B1 — Direct Didi interview: MoneyPlay
- https://www.youtube.com/watch?v=CR2OlcohX_M

The episode description explicitly indexes Didi discussing the origin/mathematics of the Didi Index and false points.
### B2 — Direct Didi interview: Contadora da Bolsa
- https://www.youtube.com/watch?v=2--DVCVP6zY

Direct interview dedicated to Agulhadas and Didi Index. It is a primary qualitative reference for terminology and visual interpretation.

### C1 — Nelogica Didi Index help
- https://ajuda.nelogica.com.br/hc/pt-br/articles/13161968774299-Didi-Index

Nelogica documents the default periods 3, 8 and 20, defines the agulhada as the three moving-average lines passing through the same candle body, and describes bullish/bearish ordering.

### C2 — Nelogica strategy-language documentation
- https://downloadserver-cdn.nelogica.com.br/content/profit/manual_ntsl/ManualNTSL.pdf
- https://downloadserver-cdn.nelogica.com.br/content/site/midias/documentacao_modulo_estrategias.pdf

The `DiDiIndex` function uses a reference average plus two other averages. The published example uses reference=8, media1=3, media2=20 and arithmetic-average type=0.

### D1 — Clear educational eBook
- https://www.clear.com.br/site/Content/pdf/download-ebooks/eBook-AnaliseTecnica.pdf

This reproduction states the directional-movement/no-trend conditions and says an agulhada should be accompanied by trend in the same direction according to ADX. Treat as strong secondary evidence, not primary authorship.

### D2 — circulating Didi/CST material
- https://www.passeidireto.com/arquivo/79194395/didi-aguiar

Contains detailed DMI/ADX explanations including the two 'no trend' cases. Parameter and timing rules from this family remain candidates until cross-validated.
### E1 — community implementation references
- https://br.tradingview.com/scripts/didiaguiar/
- https://www.mql5.com/pt/blogs/post/755751

These are useful for formalizing hypotheses such as alert/confirmation sequencing, false-point logic, ADX 32 filtering and multi-timeframe scanning. They are not allowed to define the HAGMARTK DDIX contract without stronger-source parity.

## 4. Frozen facts for DDIX v0.1 research

The following are frozen as source-supported research facts:

1. The visible project name is **HAGMARTK DDIX**.
2. The core Didi Index uses moving-average periods **3 / 8 / 20**.
3. The **8-period average is the reference axis** in the Didi Index representation.
4. Arithmetic/simple averages are the first parity baseline because Nelogica's published reference example uses arithmetic type 0 for 8/3/20.
5. A classic agulhada requires the three averages to converge through the **same candle body** or equivalently produce the characteristic near-zero crossing in the indexed representation.
6. Bullish post-needle ordering: **MA3 above MA8 above MA20**.
7. Bearish post-needle ordering: **MA20 above MA8 above MA3**.
8. The broader Didi trade-system research must include **DMI/DI+/DI-/ADX, Bollinger, TRIX and Stochastic**, not only Didi Index.
9. DMI/ADX is a trend-context component, not a decorative indicator.
10. Bollinger is a timing/context component in the published Didi course structure.
11. No DDIX Telegram alert, PAPER entry, optimization or real order is authorized at this stage.

## 5. Explicitly NOT frozen yet

The following must remain hypotheses until stronger parity evidence exists:

- exact normalization formula used by every reference implementation;
- whether all production parity must use SMA or whether other average types belong to valid variants;
- DMI/ADX period 8 and exact smoothing convention;
- whether `ADX rising and >32` is an entry gate, a strength classification, or merely one implementation choice;
- the exact Bollinger parameters and quantitative definition of 'opening';
- TRIX period/signal-average parameters and exact entry/exit semantics;
- Stochastic periods/smoothing and whether it is confirmatory or exit-only;
- deterministic definition of **Ponto Falso**;
- deterministic distinction between **alert** and **confirmation** crossings;
- definitions of **Agulhada Santa**, **Queijo Minas** and **BJMA**;
- confirmed-entry versus anticipated-entry timing;
- stop placement, trailing rules, exit on MA8/opposite average and Fibonacci objectives;
- supported market universe and production timeframes.

## 6. Research hypotheses to test — not strategy rules

These identifiers may be used only in an analysis module until promoted by evidence:

- `DDIX_NEEDLE_CLASSIC`: 3/8/20 converge in one candle body and separate in valid directional order.
- `DDIX_ALERT_FAST_CROSS`: MA3 crosses the MA8 reference before full needle confirmation.
- `DDIX_CONFIRM_SLOW_CROSS`: MA20 crossing the MA8 reference completes a candidate confirmation sequence.
- `DDIX_FALSE_POINT_CANDIDATE`: apparent fast cross contradicted by the position/slope of the slow line.
- `DDIX_TREND_OK`: DMI/ADX context supports the needle direction.
- `DDIX_BOLLINGER_TIMING_OK`: bands are opening in the directionally compatible context.
- `DDIX_MOMENTUM_OK`: TRIX and Stochastic agree with the trade direction.
- `DDIX_SANTA_CANDIDATE`: a full-system confluence candidate, definition not frozen.

Every hypothesis must expose raw values, timestamps and reason codes. No boolean-only black-box output is acceptable.

## 7. Initial mathematical parity plan

### Gate P1 — moving averages
For a fixed OHLC fixture, independently calculate SMA3, SMA8 and SMA20 from close prices and compare against Nelogica/Profit output using `DiDiIndex(8,0,3,0,20,0)`.
Acceptance: zero unexplained directional mismatch and documented numeric tolerance for the indexed lines.

### Gate P2 — classic needle geometry
Build synthetic candles where all three averages cross the same candle body, plus near-miss controls. Verify bullish and bearish ordering exactly.

Acceptance: the detector must distinguish true same-body convergence from visually close but non-equivalent cases.

### Gate P3 — direct-example parity
Capture several examples from direct Didi videos/materials with timestamp, asset/timeframe when available, and manually label the expected state.

Acceptance: DDIX research renderer must reproduce the visible 3/8/20 geometry and event classification before any historical scan.

### Gate P4 — auxiliary indicators
Only after P1-P3 pass, implement DMI/ADX, Bollinger, TRIX and Stochastic as separate evidence channels. Each gets its own source/parameter parity test.

Acceptance: no auxiliary filter may silently suppress a classic needle until its own rule is source-validated.

### Gate P5 — historical replay
Run broad replay with no Telegram and no PAPER accounting. Measure frequency, asset/timeframe distribution, false-point candidates and confluence rates.

Acceptance: statistics are descriptive only; no optimization against profit is allowed before rule fidelity is frozen.

### Gate P6 — prospective Shadow
Observe new bars only. Persist evidence, render charts, and compare manually against reference interpretation.

Acceptance: sufficient prospective sample plus zero replay/bootstrap publication defects. Telegram remains disabled until an explicit publication contract is approved.

## 8. Required evidence payload

Every future DDIX event must retain at minimum:

- symbol, provider, timeframe and closed-candle timestamp;
- OHLC of the candidate candle;
- MA3, MA8, MA20 raw price values;
- normalized/indexed line values used by the renderer;
- whether each average lies inside the candidate candle body;
- cross timestamps/order and separation direction;
- DI+, DI-, ADX and ADX slope once that module is validated;
- Bollinger upper/base/lower values and objective opening metric once validated;
- TRIX and signal-line values once validated;
- Stochastic K/D values once validated;
- source-contract version and detector version;
- bootstrap/replay/prospective flags;
- every rejection/suppression reason.

## 9. Renderer requirements

The first DDIX chart is an **evidence chart**, not a trade advertisement.

It must show:

1. price candles with SMA3/SMA8/SMA20 overlaid;
2. candidate candle clearly marked;
3. a separate Didi Index panel with the reference zero axis;
4. raw values or compact labels sufficient to audit the crossing;
5. auxiliary panels only when their formulas have passed parity;
6. no overlapping labels;
7. explicit `RESEARCH / SHADOW — NO REAL ORDER` marking.

The renderer must never call a pattern 'Agulhada Santa', 'Ponto Falso' or other named variant unless that classifier has a frozen deterministic contract.

## 10. Decision frozen at this checkpoint

**APPROVED:** begin DDIX as an isolated research module using 3/8/20 parity first.
**NOT APPROVED:** Telegram, PAPER trade simulation, scoring by profitability, parameter optimization or production strategy status.
**NEXT IMPLEMENTATION:** a pure `public_reference`/research module plus deterministic tests for moving averages, same-candle-body needle geometry and bullish/bearish ordering.

Any future change to these frozen facts requires a new source-contract revision, preserving v0.1 for auditability.

## 11. Revision v0.2 — Didi Index line parity and Ponto Falso candidate

This revision preserves v0.1 unchanged and adds two research-only contracts.

### 11.1 Indexed-line parity candidates

The zero-axis interpretation is now represented explicitly by two candidate methods:

- `ABSOLUTE`: `fast_line = SMA3 - SMA8`; `slow_line = SMA20 - SMA8`.
- `RATIO`: `fast_line = SMA3 / SMA8 - 1`; `slow_line = SMA20 / SMA8 - 1`.


`ABSOLUTE` is the current default research representation because public legacy implementations explicitly use the displacement from MA8. It is not yet claimed to be numerically identical to every Profit/Nelogica build.

Both representations preserve the source-supported sign geometry: fast above zero means MA3 > MA8; slow below zero means MA20 < MA8, and vice versa.

No tolerance, percentage threshold or optimization is frozen from these candidate representations.

### 11.2 Ponto Falso — deterministic research candidate

The CST apostila defines the concept by the exact position of the short, long and intermediate lines at the event moment, using the 'two bulls and a fence' analogy, and states that subsequent line behavior is irrelevant to identifying that moment.

A later public implementation formalizes the symmetric cases as follows:

- `FALSE_BUY`: the fast average crosses MA8 upward while MA20 is already above MA8 and is moving farther upward. The apparent buy is treated as false; continuation bias is bearish.
- `FALSE_SELL`: the fast average crosses MA8 downward while MA20 is already below MA8 and is moving farther downward. The apparent sell is treated as false; continuation bias is bullish.

HAGMARTK implements this only as `REFERENCE_CANDIDATE_CST_PLUS_COMMUNITY_FORMALIZATION`.

This is not yet an operational DDIX rule because the exact mathematical phrasing comes from secondary formalization, not from an official platform specification or a directly transcribed Didi formula.


### 11.3 Additional evidence used in v0.2

- CST apostila reproduction, section 12B, `Como encontramos um Ponto Falso`.
- Nelogica help/manual for the 3/8/20 reference-axis semantics.
- Didisofia/Agulhada.com public historical article on Ponto Falso; useful context but explicitly non-official.
- TradingView community screener exposing `Fake Buy` / `Fake Sell`; used only to formalize the candidate.
- AmiBroker public Didi Index formula using `MA3-MA8` and `MA20-MA8`; used only as implementation parity evidence.

### 11.4 Gate decision

**APPROVED FOR RESEARCH:** zero-centered DDIX line calculation and Ponto Falso candidate evidence.

**STILL NOT APPROVED:** Telegram, PAPER execution, order simulation, ADX-gated Ponto Falso, profit scoring or optimization.

Next gate: compare the candidate classifications against manually labelled examples from Didi video/course material before promoting any Ponto Falso rule beyond `REFERENCE_CANDIDATE`.
