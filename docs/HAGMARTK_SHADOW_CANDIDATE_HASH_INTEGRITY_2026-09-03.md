# HAGMARTK Shadow — Candidate Hash Integrity — 2026-09-03

Status: CONSISTENCY FIX / CANDIDATE UNCHANGED

## Finding

`RobustCandidateSpec` is the canonical source for the frozen candidate parameter hash.
Its file has not changed since the robust-candidate checkpoint (`1974256`) and was not modified by the current work.

`ShadowEvent`, however, contained an older hardcoded default hash (`a212...`) introduced in an earlier Shadow intelligence checkpoint. The runtime candidate API computes the canonical current hash as `d192dd381b33a430e8214b7a3ad1d850e03db48eb601696dc2cc57adf160955a`.

This was a stale reference in the event model, not a candidate parameter change.

## Correction

The hardcoded `ShadowEvent.parameter_hash` literal was removed.
`ShadowEvent` now references `HDF_CANDIDATE_V1_PARAMETER_HASH` directly from the canonical candidate module.

No candidate field, candidate ID, candidate version, target, entry rule, exit rule or hash algorithm was changed.
Historical database rows are not silently rewritten by this code change.

## Validation

- repository search: no remaining occurrence of the stale `a212...` literal;
- `ShadowEvent()` default hash equals `HDF_CANDIDATE_V1_PARAMETER_HASH`;
- `RobustCandidateSpec.validate_immutability()` passes against that value;
- targeted Shadow/provenance regression: **25 passed**.
