# HAGMARTK DVP — Post-Reversal Target Gate — 2026-09-03

Status: RESEARCH / NOT PROMOTED

## Source boundary

Public DIVAP material describes Fibonacci extension for targets and allows more than one construction, including pre-reversal, post-reversal and shorter moves. It does not publish one deterministic automatic anchor-selection algorithm for every case.

Therefore the test below is a HAGMARTK automation hypothesis, not a claim of original DIVAP source truth.

## Hypothesis frozen before execution

Policy ID: `POST_REVERSAL_PATTERN_RANGE_V1`.

- Use only the reversal pattern already known at confluence completion.
- Bullish: anchor A = pattern low; anchor B = pattern high; C = B.
- Bearish: anchor A = pattern high; anchor B = pattern low; C = B.
- Levels: 61.8%, 100%, 161.8%, 200%, 261.8%.
- Evaluate only occurrences that activated an entry.
- Start observation at the entry bar.
- Structural stop ends the observation.
- No 20-bar forced exit; unresolved cases remain censored.
- Same-bar target/stop is explicitly ambiguous.

## Objective criteria

The policy is not promoted by hit rate alone. It may advance only if:

1. Anchors are available deterministically for every eligible activated event with a valid reversal pattern.
2. No future candle or post-entry extremum participates in anchor selection.
3. The target ladder remains directionally ahead of entry rather than inconsistently behind it.
4. The replay produces explicit target-before-stop, stop-before-target, ambiguity and censoring counts.
5. Results are reported by level and timeframe without optimizing parameters after seeing outcomes.
6. Any management/allocation rule remains separately unresolved.

## Reproduction

`python tools/research_dvp_post_reversal_pattern_targets.py`

## Execution result

Current rolling MT5 cohort: 13 assets x 6 timeframes, 1200 candles requested per combination.

Eligible activated events after the existing strict pre-reversal Fibonacci confluence gate: **17**.

All 17 had valid pattern ranges and all five projected targets were directionally ahead of entry. There were no `BEHIND_ENTRY`, `CENSORED` or `AMBIGUOUS_SAME_BAR` results.

Target reached before structural stop:

- 61.8%: **11/17**; stop first 6/17; median 1 bar; max 22 bars.
- 100%: **11/17**; stop first 6/17; median 3 bars; max 41 bars.
- 161.8%: **7/17**; stop first 10/17; median 12 bars; max 81 bars.
- 200%: **5/17**; stop first 12/17; median 6 bars; max 144 bars.
- 261.8%: **5/17**; stop first 12/17; median 32 bars; max 163 bars.

## Decision

`POST_REVERSAL_PATTERN_RANGE_V1` **advances as a research candidate only**.

Reason: it satisfies the causal/deterministic engineering gate and fixes the inconsistency seen when the pre-reversal confluence ladder was reused as a universal target ladder. However, hit counts alone cannot identify it as the authentic or best DIVAP target construction.

No exit-management rule, partial allocation, stop movement or candidate version is changed.

## Next gate

Measure the projected target distances in R for this same fixed cohort and compare construction provenance against the remaining source-described alternatives. Do not optimize anchor selection from realized outcomes.

## Canonical frozen-snapshot audit

The earlier rolling-MT5 counts above are retained only as an audit trail and are **not the canonical comparison sample**, because the live cohort changed between sequential runs.

A single market snapshot was therefore frozen locally before recomputing outcome and R metrics together:

- Snapshot rows: **93,600**.
- Grid: 13 assets x 6 timeframes x 1,200 candles.
- Eligible activated events after the existing strict pre-reversal confluence gate: **14**.
- Evaluated target rows: **70**.
- No behind-entry target, censoring or same-bar target/stop ambiguity.

Canonical target-before-stop results:

- 61.8%: **8/14**, median 1 bar, max 4.
- 100%: **8/14**, median 2.5 bars, max 12.
- 161.8%: **4/14**, median 9 bars, max 81.
- 200%: **3/14**, median 6 bars, max 82.
- 261.8%: **3/14**, median 32 bars, max 107.

Canonical R distances in this zero-buffer/no-gap sample:

- 61.8% = **0.618R**.
- 100% = **1.000R**.
- 161.8% = **1.618R**.
- 200% = **2.000R**.
- 261.8% = **2.618R**.

This equivalence is conditional. It follows because the current default entry/stop geometry uses the two reversal-pattern extremes with zero execution and stop buffers, and the canonical sample contained no activation gap that altered entry. A gap or non-zero buffer breaks exact equality.

Canonical reproduction: `python tools/research_dvp_post_reversal_snapshot_audit.py`.
The frozen raw snapshot is stored under `data_cache/` and intentionally remains outside version control.

## Reproducibility hardening

The canonical audit now reuses the frozen snapshot by default. A normal run must report `SNAPSHOT_MODE REUSED` and reproduce the same cohort/results. A new rolling market capture is explicit only through:

`python tools/research_dvp_post_reversal_snapshot_audit.py --refresh`

This prevents accidental sample drift during sequential comparisons.
