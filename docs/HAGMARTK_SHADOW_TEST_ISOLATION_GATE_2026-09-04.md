# HAGMARTK Shadow — Test Isolation Gate — 2026-09-04

## Scope
This gate prevents pytest/TestClient/bootstrap tests from writing to the real Shadow runtime database.
It does not change candidate logic, parameters, version, parameter hash, execution rules, or publication eligibility.

## Incident
During evidence-integrity validation, scanner telemetry changed while the production backend was stopped.
The changes were traced to tests that could start a real `ShadowScannerManager` against `shadow_engine.db`.
The affected rows were operational telemetry only; HDF/Fibonacci prospective ledgers remained protected.

## Root causes
1. `backend/api/app.py` documented autostart as OFF by default for tests, but code defaulted `HAGMARTK_AUTOSTART` to `1`.
2. `tests/test_bootstrap.py` invoked `start_system()` with mock market data but no injected Shadow scanner, so a real scanner/store was created.
3. Approval metrics had only temporal exclusion for old fixtures, not an explicit fixture/test-event exclusion.

## Frozen corrections
- API autostart default changed to OFF. Production remains explicit through `START_HAGMARTK_MF.ps1` with `HAGMARTK_AUTOSTART=1`.
- System-health autostart test uses mock market data plus a no-op fake scanner.
- Bootstrap test injects a fake scanner before `start_system()`.
- `ProspectiveEligibilityFilter` rejects fixture/test ShadowEvents independently of timestamp.

## Validation
Directed isolation suite: 17 passed.
Full project regression: 497 passed, 1 skipped.
Before/after SQLite telemetry fingerprint remained identical:
- rows: 80
- successful checks: 104
- failed checks: 8
- max updated_at: `2026-09-04 10:58:05`
- live HDFEvidence: 0
- live Fibonacci telemetry: 0

Therefore pytest no longer mutates the real Shadow ledger during this gate.
