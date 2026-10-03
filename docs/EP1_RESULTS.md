# EP-1 results: of the collapsed states, only "never searched" changes an outcome

Registration: docs/EP1_PREREG.md (748a932), committed before the probe. Probe: `tools/ep1_probe.py`.
x86-64 container, Python 3.13.15. **NOT VALIDATED on the S25.** Claude-assisted (Claude Opus 5.5);
Chad gave direction only. Self-tested; not independent review.

## Failures and limits first
- No prediction failed (7 of 7). **Most of this is by construction:** F3-F7 follow from the registered world model
  (inaccessible = transient, unsearched = fixed by one search, missing/out-of-scope = never fixable). Only F1 and
  F2 are observations of the real Gate. The model is an assumption, not a measurement of any sensor or search.
- Sabotage (the generic caller is given the labels) refutes F4 and F5 and exits 1. F1-F3 and F6-F7 still hold under
  sabotage; they do not depend on what the caller knows.

## Result
```
first decision per condition:
  M  DEFER  missing_required_evidence:sensor
  I  DEFER  missing_required_evidence:sensor
  U  DEFER  missing_required_evidence:sensor
  O  DEFER  missing_required_evidence:sensor
  S  DEFER  verification_insufficient_evidence
  RM REFUSE runtime_state_unavailable
  RD ALLOW  -
outcome (final decision, retries spent):
  R=3 M  P_gen ('DEFER', 3)  P_dist ('DEFER', 0)
  R=3 I  P_gen ('ALLOW', 1)  P_dist ('ALLOW', 1)
  R=3 U  P_gen ('DEFER', 3)  P_dist ('ALLOW', 1)
  R=3 O  P_gen ('DEFER', 3)  P_dist ('DEFER', 0)
  R=3 S  P_gen ('ALLOW', 1)  P_dist ('ALLOW', 1)
  R=0 M  P_gen ('DEFER', 0)  P_dist ('DEFER', 0)
  R=0 I  P_gen ('DEFER', 0)  P_dist ('DEFER', 0)
  R=0 U  P_gen ('DEFER', 0)  P_dist ('DEFER', 0)
  R=0 O  P_gen ('DEFER', 0)  P_dist ('DEFER', 0)
  R=0 S  P_gen ('DEFER', 0)  P_dist ('DEFER', 0)
HELD    F1
HELD    F2
HELD    F3
HELD    F4
HELD    F5
HELD    F6
HELD    F7
VERDICT 7 of 7 as registered
DIGEST a866bbdc092edb138eb4fbcc737a7c5174506e1b7868d52c1d9786183b51a316
```

## What it shows
- **EP-1A, inaccessible: no different disposition needed** (under the model). Retrying fixes it, and a caller who
  only sees the Gate's generic DEFER already retries.
- **EP-1B, never searched: the collapse changes the outcome.** A caller who sees only "missing_required_evidence"
  retries 3 times and never gets the evidence; one who knows it was never searched searches once and gets ALLOW.
- **EP-1C, out of scope (and plain missing): the outcome is the same, the cost is not.** Both end not-ALLOW; the
  generic caller wastes its whole retry budget, the informed one stops at once.
- **Negative controls held:** with no retry budget every condition behaves identically under both callers (F6); and
  "inaccessible" vs "verifier says insufficient" legitimately share DEFER-and-retry (F7).
- **New observation (F2, real Gate):** a missing *runtime* value is REFUSEd (`runtime_state_unavailable`) while a
  missing *evidence* item is DEFERred. The same condition, "nobody supplied it", gets two dispositions depending on
  where it sits. Not a defect claim: both fail closed. It is an inconsistency to decide on.

## Door (M15)
Only F4 justifies a change: a distinct DEFER reason for "not searched" that a caller can act on. That is a
gate-contract change (CONTRACT.md, vectors, Go port), not registered. Under rule 6 of the closure draft it needs a
registered claim that requires it; there is none yet.
