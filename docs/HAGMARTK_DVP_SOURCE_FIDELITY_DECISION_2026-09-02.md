# HAGMARTK DVP — Source Fidelity Decision — 2026-09-02

Status: FIBONACCI AUTO-ANCHOR NOT PROMOTED

## Source-backed contract
Fernando Pereira's published DIVAP material describes four required components:
- RSI/IFR divergence;
- volume above a 20-period average;
- price at a Fibonacci extension target: 61.8, 100, 161.8, 200 or 261.8;
- reversal chart/candlestick pattern.

Entry is above the reversal pattern for buys and below it for sells; stop is on the opposite side.
The method is described as usable across markets and timeframes, with H1/H4/D1 cited as more effective in the ebook.

## Fibonacci anchor finding
The public lesson explicitly presents more than one valid way to draw the extension:
- extrema before the reversal;
- extrema after the reversal;
- a shorter movement for a more conservative target set.
The practical discussion also uses minima/maxima around the reversal.

Therefore the public source does not establish one unique deterministic automatic anchor selector.
A backtest that searches multiple historical pivot pairs until one level touches price would introduce hindsight.
The current `latest completed leg` selector is consequently a HAGMARTK research hypothesis, not a recovered original rule.

## Frozen decision
Do not claim exact DIVAP Fibonacci fidelity and do not emit complete HAGMARTK DVP events from that selector yet.
Keep the four-confluence promotion gate closed until either:
1. a primary source establishes a unique forward-knowable anchor rule; or
2. HAGMARTK deliberately versions and validates its own deterministic Fibonacci policy without claiming it is identical to the original discretionary method.
