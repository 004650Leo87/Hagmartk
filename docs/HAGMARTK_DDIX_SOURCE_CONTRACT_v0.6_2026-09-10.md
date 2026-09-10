# HAGMARTK DDIX v0.6 — Source Contract

Date: 2026-09-10
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


## 11. v0.3 — source-anchor parity checkpoint

Gate P3 is now split into two independent claims:

- **semantic/source parity**: the source explicitly supports the interpretation;
- **numeric/visual parity**: the DDIX implementation reproduces the exact plotted reference geometry/values.

These claims must never be conflated.

### Official Nelogica visual anchor
The Nelogica Didi Index help page explicitly documents the reference axis as the 8-period average and the post-signal sign ordering:

- bullish: MA3 above zero, MA8 on the reference axis, MA20 below zero;
- bearish: MA3 below zero, MA8 on the reference axis, MA20 above zero.

This supports a deterministic `IndexedAlignment` classifier. It does **not** prove the numeric normalization formula used internally by Profit.
### Direct-video semantic anchors
The public video `DIDI Agulhada PARTE 1/3` is registered with timestamps for manual review:

- `01:22:04` — discussion of agulhadas and graphical algorithms;
- `01:30:08` — discussion of false/misleading movements;
- `02:07:41` — trend context and false points, including the importance of multiple timeframes.

These timestamps are **semantic anchors only**. No OHLC, MA values, line coordinates or screenshot checksum was available from the public transcript/index, so none may be labeled as numeric visual parity.

### CST false-point anchor
Section 12B of the circulating CST apostila remains the strongest detailed textual anchor found for Ponto Falso. It emphasizes the **exact instant** when the fast line attempts to cross the reference while the long line is positioned/moving away on the opposite side.

The current deterministic classifier remains `REFERENCE_CANDIDATE_CST_PLUS_COMMUNITY_FORMALIZATION`; it is not promoted to an operational rule by this checkpoint.
### Gate P3 status

**PASS — semantic sign/order parity:** official Nelogica documentation and visual example support the bullish/bearish indexed ordering.

**PASS — source-anchor registry:** direct-video/CST anchors are versioned with provenance and cannot silently become production rules.

**OPEN — numeric Profit parity:** the exact transformation from MA3/MA8/MA20 to plotted Didi Index values remains unproven. The local workstation has no Profit/Nelogica installation available for an independent numeric comparison.

**OPEN — frame-level Ponto Falso parity:** public transcript material provides semantics and timestamps, but not the raw frame/indicator values needed for pixel/numeric acceptance.

### v0.3 frozen decision

`IndexedAlignment` may be used as research evidence only. It must never be treated as an Agulhada by itself; an agulhada still requires convergence/cross timing evidence. Ponto Falso remains a reference candidate. DDIX Telegram, PAPER execution, profitability scoring and parameter optimization remain disabled.

Next gate: obtain reproducible Profit/Nelogica output or another direct numeric reference fixture; then validate the index formula before auxiliary DMI/ADX/Bollinger/TRIX/Stochastic filters can suppress or qualify events.

## 11. v0.4 — Official visual evidence and DMI semantic gate

### 11.1 Official Profit/Nelogica visual evidence
Nelogica's official Didi Index examples show the 8-period reference as a zero axis and the two moving lines oscillating above/below it. The displayed line values are in a scale consistent with price-distance representation, strengthening the absolute-distance hypothesis:

- fast line candidate: `MA3 - MA8`;
- slow line candidate: `MA20 - MA8`;
- reference axis: `0`.

Evidence:
- https://ajuda.nelogica.com.br/hc/article_attachments/13175815276059
- https://ajuda.nelogica.com.br/hc/article_attachments/13176012179739
- https://ajuda.nelogica.com.br/hc/pt-br/articles/13161968774299-Didi-Index

Decision: `ABSOLUTE` is promoted from generic community candidate to **PRIMARY_PARITY_HYPOTHESIS**. Exact numeric parity with Profit remains OPEN until the underlying OHLC sequence can be reproduced against `DiDiIndex(8,0,3,0,20,0)`.

`RATIO` remains only as a laboratory control and must not be used by any operational DDIX classifier.

### 11.2 DMI/ADX semantic interpretation
The Didi/CST material and independent educational reproductions agree on these semantic rules:

- `DI+ > DI-` => bullish directional context;
- `DI- > DI+` => bearish directional context;
- no trend when ADX is below both DI lines;
- no trend when ADX is falling and `ADX <= 32`;
- outside those two no-trend cases, trend is considered present, whether strong or weak;
- an ADX rise followed by a turn downward is a `kick` candidate and may indicate exhaustion/top-bottom context.

Calibration `DMI=8 / ADX=8` is retained as a **strong source-supported parameter candidate**, not yet a platform-parity proof.
### 11.3 Implementation boundary
Implemented research-only module:
`backend/strategies/ddix/dmi_reference.py`

The module classifies already-supplied `DI+`, `DI-` and `ADX` values. It deliberately does **not** calculate DMI/ADX yet, because platform smoothing/parity is a separate technical question.

Required behavior:
- expose direction, ADX slope, both no-trend conditions and reason codes;
- fail closed for invalid/non-finite values;
- preserve the exact `<= 32` condition separately from generic ADX thresholds such as 20/25;
- expose an ADX-kick candidate only as evidence, not as an automatic exit.

No DDIX needle may be suppressed, promoted, published or traded from this DMI module at v0.4.

### 11.4 Source references added in v0.4
- Nelogica official Didi Index help and screenshots.
- Nelogica official ADX/DI+/DI- help.
- Apostila CST / Doji Star calibration reproduction.
- Clear educational eBook reproduction of the two no-trend cases.
- Didi Aguiar eBook reproduction describing DI direction, ADX <=32 rule and ADX kick.

### 11.5 Next gate
Implement DMI/ADX **calculation parity harnesses** as competing research implementations (Wilder reference versus provider/platform output) without allowing either implementation to affect DDIX decisions.

After DMI numeric parity, proceed independently to Bollinger 8 ±2, TRIX 9/4 and Stochastic 8/3/3, each with its own provenance and parity tests.

## 12. v0.5 — DMI/ADX calculation parity gate

### 12.1 Authoritative formula contract
MetaQuotes documents `iADXWilder` as the Average Directional Movement Index by Welles Wilder and exposes buffers `MAIN_LINE`, `PLUSDI_LINE`, and `MINUSDI_LINE`.

Published formula reference:
- https://www.mql5.com/en/docs/indicators/iadxwilder
- https://www.mql5.com/en/code/8

The research implementation follows the published sequence: raw true range and directional movements, SMMA smoothing, `+DI/-DI`, `DX`, then `ADX = SMMA(DX)`.

Gate status: `FORMULA_SPEC_PASS`.

### 12.2 Independent implementations
Two deliberately independent paths now exist in `backend/strategies/ddix/dmi_wilder.py`:

- batch calculation over a fixed OHLC sequence;
- streaming bar-by-bar recurrence with its own raw TR/DM and smoothing calculations.

Acceptance requires bar-by-bar agreement after the same initialization contract.
Gate status: `INDEPENDENT_IMPLEMENTATIONS_PASS`.

### 12.3 External numeric fixture
A public QuantInsti Wilder calculation example is retained as an external arithmetic fixture:
- https://blog.quantinsti.com/adx-indicator-python/

For its period-5 monotonic example, the published `+DI` sequence begins at `68.80733945` and progresses through `71.88498403`, `74.22308546`, `77.37420531`, `80.43684038`, and `83.74053399`; the published ADX reaches `100`.

The DDIX batch implementation reproduces those published directional values within numeric tolerance.
Gate status: `EXTERNAL_NUMERIC_FIXTURE_PASS`.

### 12.4 Live MT5 buffer probe
A read-only MQL5 probe was compiled successfully:
`tools/ddix/DDIX_ADXWILDER_PROBE.mq5`

Safety contract:
- no trade library or order function;
- `AllowLiveTrading=0`;
- `AllowDllImport=0`;
- separate idle 4xCube MT5 installation;
- Pepperstone operational terminal not touched;
- automatic terminal shutdown after script completion.

The isolated terminal loaded the script on `EURUSDxx/M15`, but its stored Tickmill-Demo authorization was stale/invalid. No platform CSV was produced, and the terminal exited normally.

Gate status: `LIVE_MT5_BUFFER_BLOCKED_BY_STALE_LOGIN`.
This is not evidence of an algorithm mismatch and must not be reported as a parity failure.

### 12.5 Platform comparator
`backend/strategies/ddix/dmi_platform_parity.py` loads the probe CSV and compares MT5 `ADX/+DI/-DI` against the research calculation after a configurable warmup. It reports maximum absolute error per line and fails closed on insufficient or invalid data.

The comparator itself is tested, but it does not constitute platform parity until fed a genuine MT5 export.

### 12.6 Frozen decision
DMI/ADX semantic rules remain research-supported, but **must not yet gate DDIX needles**.

Current statuses:
- formula specification: PASS;
- independent batch/stream calculations: PASS;
- external numeric fixture: PASS;
- genuine MT5 `iADXWilder(8)` buffer parity: OPEN/BLOCKED;
- Telegram DDIX: OFF;
- PAPER DDIX: OFF;
- real-order execution: NOT AUTHORIZED.

Next allowed step: obtain a genuine read-only platform buffer from a valid non-operational MT5 session, or an equally authoritative numerical platform export. Only after that may DMI/ADX be promoted from evidence channel to DDIX qualification gate. Bollinger/TRIX/Stochastic remain downstream gates and must not be used to bypass this parity requirement.

## 13. v0.6 — Bollinger research gate

### 13.1 Source-supported parameters
The Didi/CST material consistently gives Bollinger period `8` and deviations `-2/+2` as the calibration used in the method.

Primary/secondary evidence used at this checkpoint:
- https://pt.scribd.com/document/633888572/Apostila-Didi-CST-pdf
- https://www.scribd.com/document/697306680/eBook-Didi-Aguiar
- https://www.agulhada.com/como-funciona

This calibration is promoted to **SOURCE_SUPPORTED_PARAMETER_CANDIDATE**, not yet to a provider-parity proof.

### 13.2 Formula baseline
Nelogica publishes the band-width relation as:
`((upper - lower) / middle) * 100`.

MetaQuotes publishes Bollinger construction around a moving average and standard deviation, and its standard-deviation reference uses divisor `N`, not `N-1`.

References:
- https://ajuda.nelogica.com.br/hc/pt-br/articles/360049960572-Bollinger-Band-Width
- https://www.mql5.com/en/docs/indicators/ibands
- https://www.mql5.com/en/code/49

### 13.3 Objective opening candidate
Didi's material describes the useful phase as the bands beginning to open and the rally weakening/ending when the bands begin to close.

The research classifier therefore exposes, separately:
- width increasing/decreasing;
- upper band rising;
- lower band falling;
- `mouth_opening_candidate = width increasing AND upper rising AND lower falling`;
- `mouth_closing_candidate = width decreasing`.

This is an **objective research translation**, not yet a frozen Didi operational rule.

A visual angle such as `120°–180°` is deliberately NOT encoded. Screen angle changes with chart scale, aspect ratio and zoom and therefore is not a stable mathematical feature.

### 13.4 Implementation boundary
Implemented:
`backend/strategies/ddix/bollinger_reference.py`

The module computes SMA-based period-8 / deviation-2 snapshots, population standard deviation, raw width and Nelogica-style percentage width, then classifies opening/closing geometry.

It does not create an entry, reject a needle, score profitability, publish Telegram messages or create PAPER operations.

### 13.5 Gate status
- `BOLLINGER_PARAMETER_SOURCE_SUPPORT = PASS`
- `BOLLINGER_FORMULA_BASELINE = PASS`
- `BOLLINGER_WIDTH_METRIC = PASS`
- `BOLLINGER_MOUTH_OBJECTIVE_TRANSLATION = RESEARCH_CANDIDATE`
- `BOLLINGER_PLATFORM_BUFFER_PARITY = OPEN`
- `BOLLINGER_OPERATIONAL_FILTER = NOT_APPROVED`

### 13.6 Next gate
Proceed to TRIX independently. Validate the period-9 / signal-average-4 calibration, the exact TRIX calculation convention and the crossing semantics before allowing TRIX to qualify any DDIX needle.

Bollinger remains evidence-only until a later confluence contract explicitly promotes it.
