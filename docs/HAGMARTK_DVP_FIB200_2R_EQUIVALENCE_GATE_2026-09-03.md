# HAGMARTK DVP — Fibonacci 200% vs 2R Equivalence Gate — 2026-09-03

Status: RESEARCH / NOT PROMOTED

## Question

Determine whether the post-reversal pattern-range Fibonacci 200% target is genuinely equivalent to the HAGMARTK `EXIT_2R` benchmark, and freeze the exact boundary where equivalence fails.

## Definitions

Let:

- `W = pattern_high - pattern_low`, with `W > 0`.
- `g` = effective entry displacement beyond the broken pattern extreme in trade direction. It includes any non-zero execution buffer and any additional activation gap.
- `s` = stop buffer beyond the opposite pattern extreme.
- `lambda` = Fibonacci extension level expressed as a ratio, e.g. 2.0 for 200%.

For both bullish and bearish geometry:

- initial risk `R = W + g + s`;
- distance from real entry to Fibonacci target = `lambda * W - g`;
- Fibonacci target expressed in R = `(lambda * W - g) / (W + g + s)`.

## Algebraic consequence

For `lambda = 2.0`:

`Fib200_R = (2W - g) / (W + g + s)`.

Exact equality `Fib200_R = 2` requires:

`2W - g = 2W + 2g + 2s`

therefore:

`3g + 2s = 0`.

Because `g >= 0` and `s >= 0`, exact equality exists **only when `g = 0` and `s = 0`**.

The HAGMARTK 2R benchmark is farther from entry than Fib200 by a price distance of exactly:

`3g + 2s`.

Thus any execution buffer, activation gap or stop buffer breaks exact Fib200/2R equivalence.

## Canonical frozen-snapshot result

Using the same frozen 93,600-candle snapshot from the post-reversal target audit:

- Eligible events: **14**.
- Events with non-zero effective entry displacement `g`: **0**.
- Events with non-zero stop buffer `s`: **0**.
- Exact Fib200 = 2R events: **14/14**.
- Fib200 R range: **2.0000 to 2.0000**.
- Maximum algebra/model error for Fib200_R: **0.0**.
- Maximum algebra/model error for the 2R-vs-Fib200 price difference: **0.0**.

This establishes exact equivalence **for this frozen sample under current zero-buffer/no-gap geometry only**.

## Controlled boundary examples

With normalized pattern width `W = 1`:

- `g=0.05, s=0`: Fib200 becomes **1.857143R**; the 2R benchmark is 0.15 price units farther.
- `g=0, s=0.05`: Fib200 becomes **1.904762R**; the 2R benchmark is 0.10 farther.
- `g=0.05, s=0.05`: Fib200 becomes **1.772727R**; the 2R benchmark is 0.25 farther.
- `g=0.25, s=0`: Fib200 becomes **1.400000R**.

## Decision

The statement **"Fib200 equals 2R" is accepted only as a conditional geometry fact**, not as a universal DIVAP or HAGMARTK exit rule.

Frozen boundary:

- If `g = 0` and `s = 0`, Fib200 = 2R exactly.
- If `g > 0` or `s > 0`, Fib200 < 2R.
- If `g >= 2W`, the Fib200 level is at or behind the real entry and cannot serve as a forward 2R target.

Consequences:

1. `EXIT_2R` remains a HAGMARTK benchmark.
2. Fib200 remains a source-level target from the post-reversal research construction.
3. They may coincide numerically in zero-buffer/no-gap cases without becoming the same rule or provenance.
4. Future execution-buffer, stop-buffer or slippage/gap policies must keep the two concepts distinct.

Reproduction: `python tools/research_dvp_fib200_2r_equivalence.py`.
