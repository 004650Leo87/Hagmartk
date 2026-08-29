# HAGMARTK MF — Optional Tooling Registry

Status: AVAILABLE CANDIDATES / NOT CORE DEPENDENCIES

The user has access to n8n, Obsidian, Buffer and Floot. Their availability is recorded now to prevent future reinvention, but none is allowed to become a mandatory runtime dependency without a concrete capability and exit path.

## Intended roles

- n8n: workflow orchestration around publication, notifications, approvals and non-critical integrations.
- Obsidian: human-readable research notes, strategy dossiers, ADRs and knowledge export; Git remains source of truth for executable contracts.
- Buffer: downstream social distribution after Publication API gates; never a source of market truth and never allowed to mutate research/trading state.
- Floot: optional application/deployment accelerator for isolated products or interfaces when it measurably reduces implementation effort without fragmenting the HAGMARTK source of truth.

## Admission rule

A tool enters implementation only when mapped to a real `capability_id`, with input/output contract, security boundary, cost, data ownership, failure mode and replacement/exit strategy documented.

No tool is introduced merely because an account exists. Core quantitative logic, Evidence Ledger, Event Engine and market-data provenance must remain portable and vendor-independent.
