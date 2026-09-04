# HAGMARTK MF — Product Registry V1 — 2026-09-03

Status: IMPLEMENTED / READ-ONLY PRODUCT CONTRACT

## Purpose

The Product Registry separates real product contracts from technical factories, benchmarks and experimental helpers.

It implements Product North build-order item 4 together with the canonical Market Event schema.

## Strategy Contract Registry

Registered product strategies only:

1. `hagmartk_divergence_flow` v1.0.0
   - candidate: `hdf_dvp_exit_2r`
   - stage: `SHADOW`
   - publication capability: `GATED`
   - real order execution: disabled
   - canonical parameter hash is inherited from `HDF_ROBUST_CANDIDATE_V1`.
2. `cycle_theory_v111_fidelity` v111.00
   - stage: `FIDELITY`
   - publication capability: `NONE`
   - real order execution: disabled

Strategy Lab benchmarks/reference implementations are deliberately excluded from the product registry.

## Evidence Contract Registry

Registered evidence contracts:

- `HDF_SHADOW_EVIDENCE_V1`: Shadow evidence from `shadow_hdf_evidence`; may support a future Quant Event only through the declared publication gate.
- `HDF_FIBONACCI_RESEARCH_V1`: research-only Fibonacci telemetry; cannot independently support a Quant Event.
- `CYCLE_THEORY_V111_FIDELITY_EVIDENCE`: research/fidelity evidence from the V111 parity documents/tests; cannot support a Quant Event.

Every evidence key referenced by a product strategy must resolve to a registered evidence contract.

## Read-only API

- `GET /api/registry/strategies`
- `GET /api/registry/evidence`
- `GET /api/registry/event-protocol`

POST, PUT and DELETE are not implemented and must return Method Not Allowed.

## Validation

- Event Protocol schema tests: PASS.
- Strategy Contract Registry tests: PASS.
- Evidence Contract Registry tests: PASS.
- Registry API tests: PASS.
- Combined registry/protocol targeted suite: 28 PASS.
- Full project regression: **467 passed, 1 skipped**.

No UI surface, external publication adapter or live-order capability was added.
