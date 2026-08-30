# Cycle Theory V111 — Gate 3Z Real Execution History

**Date:** 2026-08-30
**Status:** READ-ONLY BROKER EVIDENCE / NOT V111-SPECIFIC

## Purpose
Use already-existing MT5 order/deal history to test whether idealized replay assumptions match real broker execution, without creating or modifying any order.

## Evidence
A 180-day read-only Tickmill-Live query joined `history_orders_get` to `history_deals_get` by order ticket.

- 6 filled LIMIT-order pairs were found on XAUUSD.
- All 6 had non-zero difference between recorded order price and deal price.
- Observed limit-fill delta range: -0.19 to +0.59 price units.
- 60 SL/TP-linked order/deal pairs were found across XAUUSD, BTCUSD and US500.
- 55 of 60 had non-zero difference between recorded order price and deal price.
- Observed SL/TP delta range: -32.75 to +2.87 price units across mixed symbols.

These are broker-history observations, not Cycle Theory trades and not a universal future slippage distribution.
## Consequence
The current replay contracts that fill pending limits at the submitted limit price and protective exits exactly at SL/TP are not broker-faithful execution models. Historical broker evidence proves real execution can differ from the recorded order/trigger price.

Therefore:
- Pending fill trigger/fill semantics move from MODELLED to PARTIAL.
- SL/TP execution moves from MODELLED to PARTIAL.
- Slippage/gaps move from MODELLED to PARTIAL as an observed broker phenomenon, while no strategy-specific distribution is inferred.
- Exact-limit and exact-SL/TP fill behavior remains deliberately frozen in the research harness only as an idealized model, not as expected live economics.

No `order_send`, modification, cancellation, account number, password or secret was used by the evidence harness.
