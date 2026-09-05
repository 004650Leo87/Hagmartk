# CYCLE THEORY V111 ? PROSPECTIVE SHADOW RELEASE

Date: 2026-09-04
Status: SHADOW / PAPER / PRIVATE TELEGRAM / NO REAL ORDERS

## Frozen strategy identity

- strategy: `cycle_theory_v111_fidelity`
- source version: `111.00`
- candidate: `cycle_theory_v111_baseline`
- candidate version: `1.0.0`
- parameter hash: `a538c37c26282ab62e36ce1c1c5c826e11aee2370c8ed4ecffdaba7f145ccf85`
- source SHA-256: `32814ecf0a1ca6577f93d99e1bab358f92eed875314bc5c180ca77bc769096a2`

The 30 V111 input defaults remain unchanged. Promotion to Shadow changes observation/publication state only.

## User-approved timeframe policy

Operational prospective observation follows this policy:

1. On the Sunday weekly reopening, weekend-closed instruments are evaluated on **M15**.
2. The first V111 PAPER order generated across the weekly-opening universe consumes the opening phase.
3. Subsequent new cycles switch to **M5**.
4. If no opening trade is produced on Sunday, Monday-Friday observation is **M5**.
5. 24/7 instruments (broker paths `Cryptos\` or `24-7\`) remain **M5** because they have no weekly reopen.

This scheduling policy is a HAGMARTK operating wrapper around the frozen V111 rules; it does not alter V111 calculations.

## Market universe

The scanner discovers the live broker catalog dynamically. At release inspection Tickmill-Live exposed **117 symbols** spanning Forex, indices, metals, energy, crypto and commodities.

No hard-coded 13-symbol allowlist is used for Cycle Theory Shadow. A symbol is observed when the provider exposes quote/candle data. Closed/unavailable markets are waited on rather than treated as strategy failure.

## Prospective event lifecycle

All V111 telemetry is retained in the isolated SQLite ledger `data_cache/cycle_theory_shadow.db`. Private Telegram notification is limited to meaningful market/lifecycle transitions:

- expansion direction identified;
- setup reversal;
- expansion confirmed;
- PAPER order generated;
- virtual limit filled;
- pullback missed/cancelled;
- partial;
- breakeven;
- target level;
- final target;
- stop;
- PAPER position closure.

Channel/counting/reset telemetry remains auditable locally but is not pushed to Telegram to avoid notification noise.

## Telegram presentation

Cycle Theory messages use the approved HTML hierarchy and Portuguese copy. They expose:

- symbol and timeframe;
- buy/sell direction;
- channel high/low;
- expansion level;
- PAPER entry and stop when available;
- V111 target levels 1, 2 and 3;
- factual motor interpretation;
- explicit `SHADOW / PAPER` and `Ordem real: N?O`.

No target probability is invented. Until a prospective calibration exists, the message explicitly says `Probabilidade de alvo: n?o calibrada`.

## Safety boundary

The runtime uses `MockBroker` plus observed MT5 market data. It does not call MT5 `order_send`, `Buy`, `Sell`, pending-order submission, cancellation or position modification on the real account.

Real broker execution remains forbidden. The scanner's only external side effect is the approved private Telegram notification channel.

## Recovery and audit

- events are append-only and deduplicated by deterministic event identity;
- weekly-opening policy state is persisted;
- PAPER position/pending-order/state snapshots are checkpointed for process restart recovery;
- candidate/source hashes remain externally auditable;
- runtime status exposes `real_order_execution_enabled=false`.
