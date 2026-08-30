# Cycle Theory V111 — Gate 3V Broker Cost Observation

**Date:** 2026-08-30
**Status:** READ-ONLY BROKER EVIDENCE / NOT A STRATEGY COST MODEL

## Purpose
Characterize whether the connected account shows a stable commission-per-volume relationship in recent real deal history, without attributing those trades to Cycle Theory and without applying the observation to replay results.

## Method
- Source: connected MT5 terminal, Tickmill-Live.
- Window: previous 90 days.
- Read-only function: `history_deals_get`.
- Commission normalization: `deal.commission / deal.volume` for non-zero commission deals.
- Swap normalization: `deal.swap / deal.volume` for non-zero swap deals.
- No account number queried or recorded.
- No order sent, modified or closed.

## Observed evidence
| Symbol | Deals | Non-zero commission deals | Commission/lot values | Non-zero swap deals |
|---|---:|---:|---:|---:|
| XAUUSD | 122 | 122 | -USD 3.00/lot per recorded deal | 1 |
| BTCUSD | 14 | 0 | none observed | 0 |
| US500 | 2 | 0 | none observed | 0 |

The single non-zero XAUUSD swap observation normalized to -USD 54.00/lot for that deal. One observation is insufficient to infer overnight swap rules, direction, duration or day-of-week effects.

## Interpretation
The XAUUSD commission observation is remarkably consistent inside this historical sample, but it is still account/broker/time-window evidence rather than a guaranteed future tariff. It does not prove that Cycle Theory generated any of these deals and must not be used to label existing replay output as net-realistic.

A future versioned cost model may use broker/account/symbol evidence only after effective-date, side/entry treatment and reproducibility are explicitly contracted. Swap remains insufficiently characterized.

## Parity consequence
`Commission/swap` remains PARTIAL. The blocker is no longer whether commission can exist or whether a per-volume pattern can be observed; the blockers are cost-model versioning, current tariff validity, swap characterization and integration into the strategy ledger without contaminating historical claims.
