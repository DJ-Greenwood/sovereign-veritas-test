# JG-1 results: five input-handling defects reported by James Greenwood

The registration is [`JG1_PREREG.md`](JG1_PREREG.md), committed alone at `8a1f06e` before any fix or
probe existed. The findings are James Greenwood's, with Gemini; his report is
[preserved verbatim](external/greenwood_2026-10-03_challenge-and-audit-report.md). The fixes, the
predictions and the probe are this project's.

## What could have gone wrong, first

- **Self-tested.**
  - Claude (Opus 5.5) wrote the fixes, the predictions, the probe and its sabotage shims.
  - Nobody else has reviewed the fixes. Human review: direction only.
- **The pre-fix behaviour was seen before registration.** The registration lists it as observation
  (retrodiction), not as prediction. Only P1–P7, about the fixed code, were predictions.
- **The sabotage shims are re-implementations of the pre-fix behaviour,** written for the probe. They
  match the pre-fix outputs observed at `4eda7d4` (compare the registration's pasted output with the
  sabotage run below), but they are not the old code itself.
- **Reach.**
  - None of the five is on the Gate's decision path.
  - `AssessedEvidenceState` and `AssessedDomainReview` are used nowhere in this repository and are not
    exported.
  - The fixes matter for outside callers and for future use, not for any shipped decision.
- **Behaviour changes a caller could notice** (both deliberate, both fail-closed):
  - **F1:** `"hot"` now gives constrained search (it gave full), and any status or budget outside the
    vocabulary now stops the search (it gave full).
  - **F2:** authorizing an unregistered capability now records `REFUSE` with verification `FAIL`. It
    used to record `ALLOW`.
- **Not done:** section 6 of the report is unchecked; Greenwood's Windows run was not repeated here.
  Everything here is NOT VALIDATED on the S25.

## Raw output

`results/jg1/run.txt`, from the fixed code, on Linux with Python 3.13:

```
HELD    P1  {"5/available": 0, "CRITICAL/available": 0, "None/None": 0, "bogus/available": 0, "cool/available": 4, "critical/available": 0, "high/available": 2, "hot/available": 2, "normal/EXHAUSTED": 0, "normal/available": 4, "normal/normal": 0, "warning/available": 2}
HELD    P2  {"records": 2, "registered_authorized": true, "registered_decision": "ALLOW", "registry_has_unregistered": false, "unregistered_decision": "REFUSE", "unregistered_returns": "None", "unregistered_status": "FAIL"}
HELD    P3  {"SUPPORTED_no_assessor": "raises ValueError", "SUPPORTED_with_assessor": "constructs SUPPORTED", "UNVERIFIED_no_assessor": "constructs UNVERIFIED", "supported": "raises ValueError"}
HELD    P4  {"NOT_REVIEWED_no_reviewer": "constructs NOT_REVIEWED", "REVIEWED_no_reviewer": "raises ValueError", "REVIEWED_str_with_reviewer": "constructs REVIEWED", "unknown_status": "raises ValueError"}
HELD    P5  {"ct_0.9": 0.7, "ct_1": 0.7, "ct_1.5": 0.5, "ct_True": 0.5, "ct_str": 0.5, "iv_finite": 0.7, "iv_inf": 0.5, "nc_0.12": 0.6, "nc_True": 0.5, "nc_inf": 0.5, "nc_nan": 0.5}
VERDICT 5 of 5 as registered
DIGEST f1ab40e043ef7753d16cbf9b44a2dbba03bd56fe40f97ba2d296ef3fbf0398b7
RECORDED not pinned yet
exit 0
SABOTAGE: the five functions are replaced by their pre-fix behaviour
REFUTED P1  {"5/available": 4, "CRITICAL/available": 4, "None/None": 4, "bogus/available": 4, "cool/available": 4, "critical/available": 0, "high/available": 2, "hot/available": 4, "normal/EXHAUSTED": 4, "normal/available": 4, "normal/normal": 4, "warning/available": 2}
REFUTED P2  {"records": 2, "registered_authorized": true, "registered_decision": "ALLOW", "registry_has_unregistered": false, "unregistered_decision": "ALLOW", "unregistered_returns": "None", "unregistered_status": "PASS"}
REFUTED P3  {"SUPPORTED_no_assessor": "raises AttributeError", "SUPPORTED_with_assessor": "constructs 'SUPPORTED'", "UNVERIFIED_no_assessor": "constructs UNVERIFIED", "supported": "constructs 'supported'"}
REFUTED P4  {"NOT_REVIEWED_no_reviewer": "constructs NOT_REVIEWED", "REVIEWED_no_reviewer": "constructs REVIEWED", "REVIEWED_str_with_reviewer": "constructs 'REVIEWED'", "unknown_status": "constructs 'APPROVED'"}
REFUTED P5  {"ct_0.9": 0.7, "ct_1": 0.7, "ct_1.5": 0.5, "ct_True": 0.7, "ct_str": 0.7, "iv_finite": 0.7, "iv_inf": 0.7, "nc_0.12": 0.6, "nc_True": 0.6, "nc_inf": 0.6, "nc_nan": 0.5}
VERDICT 0 of 5 as registered
DIGEST 465651cc205c44c141bc99153e880aa913d1dc2d9eb263ce10e512795f01a313
sabotage exit 1
```

`results/jg1/p6_run.txt`:

```
$ python -m pytest -q
450 passed, 1 skipped in 41.98s
$ python tools/gate_contract.py --check kernel
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
$ python tools/gate_contract.py --check verifier
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
```

After the pin and the two new tests: `python -m pytest -q` gives 452 passed, 1 skipped.

## Predictions

| ID | Outcome |
|---|---|
| P1 `branch_factor` fails closed | **HELD** |
| P2 an unregistered authorization is refused and recorded truthfully | **HELD** |
| P3 `AssessedEvidenceState` coerces and requires `assessed_by` | **HELD** |
| P4 `AssessedDomainReview` coerces and requires `reviewed_by` for REVIEWED | **HELD** |
| P5 only finite real numbers earn quality credit | **HELD** |
| P6 existing tests unmodified and passing (450 passed, 1 skipped); Gate digest unchanged | **HELD** |
| P7 sabotage: P1–P5 each REFUTED, exit 1 | **HELD** |

**VERDICT 7 of 7 as registered.** These predictions describe the fixed behaviour; this is not a claim
that the components are now correct in general. The pinned outcome is
`RECORDED = ((True,)*5, "f1ab40e0…")`, and CI checks it, along with the sabotage control's exit 1.

## What it shows, and does not show

- **Implementation:** each reported input now gets a fail-closed result, and each pre-fix behaviour,
  restored, is caught by the probe.
- **Empirical:** NOT RUN. No real caller was affected or measured.

## Next unrun test

Check section 6 of the report line by line: canonical JSON on every evidence path, and whether
signature verification is required on every consumer path.
