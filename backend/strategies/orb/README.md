# HAGMARTK ORB v1

Independent deterministic implementation of `ORB_OPENING_RANGE_15M_5M_2R` v1.0.0.

The package intentionally separates:
- configuration / immutable identity;
- instrument + calendar validation;
- signal mathematics;
- entry/risk mathematics;
- OHLC reference execution assumptions;
- session state/idempotency;
- append-only ledger primitives;
- statistics.

No component in this package sends broker orders. Live execution adapters are outside this module and must remain disabled until explicitly promoted through HAGMARTK governance.
