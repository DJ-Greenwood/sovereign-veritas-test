# Phase 1: Epistemic Implementation Contract

**Date**: 2026-10-01  
**Status**: Implementation in progress  
**Purpose**: Establish durable, falsifiable boundaries for Phase 1 epistemic layer work

---

## 1. Purpose

Phase 1 adds a typed epistemic representation that preserves evidence, counter-evidence, contestation, assessment provenance, and unresolved disagreement alongside the existing authorization decision.

**Authorization semantics remain unchanged.**

The Gate continues to operate exactly as before. ALLOW/DEFER/REFUSE decisions are not affected by the epistemic layer in Phase 1. The new structures exist to preserve information that was previously discarded, without changing how decisions are made.

---

## 2. Repository Invariants (Non-Negotiable)

These contracts are not modified by Phase 1:

- **Gate semantics**: Unchanged. The Gate evaluates exactly as before.
- **Authorization decisions**: ALLOW / DEFER / REFUSE semantics unchanged.
- **Package hashing and replay**: Existing `package_digest()` and verification machinery unchanged. Epistemic data is automatically included because it flows through EvidenceRecord.to_dict().
- **Dataclass/serialization conventions**: Follow existing patterns. Use `frozen=True`, `_freeze()/_thaw()`, `object.__setattr__()` in `__post_init__()`.
- **VerificationStatus semantics**: Unchanged. "REFUTED" continues to mean "verifier concluded prediction is false."
- **Backward compatibility**: Packages without `epistemic` field remain valid and readable. `epistemic` is optional in EvidenceRecord constructor.

---

## 3. Epistemic Boundary: Three Independent Layers

**L1 — Computational Verification**

> Did the recorded computation execute according to the specified rules?

- Existing layer
- Examples: PASS, FAIL, REFUTED (verifier concluded prediction is false)
- Represented in: `verification.status` (VerificationStatus enum)

**L2 — Evidentiary Support**

> Does the available evidence support the claim?

- New layer
- States: UNVERIFIED, SUPPORTED, NOT_SUPPORTED, REFUTED, CONTESTED, UNKNOWN, STALE
- Requires provenance (assessed_by, assessment_method) for SUPPORTED, NOT_SUPPORTED, REFUTED
- Represented in: `epistemic.evidence_support` (AssessedEvidenceState dataclass)

**L3 — Domain Appropriateness**

> Are the evidence, assumptions, rules, and interpretation appropriate for the real-world decision?

- New layer
- States: NOT_REVIEWED, REVIEWED, REQUIRES_REVIEW
- Requires provenance (reviewed_by, review_method) for REVIEWED
- Represented in: `epistemic.domain_review` (AssessedDomainReview dataclass)

**Critical invariant**: L1 passing does not imply L2 support. L2 support does not imply L3 approval.

```python
# Valid and expected:
L1: PASS
L2: SUPPORTED
L3: REQUIRES_REVIEW
```

This demonstrates genuine independence. SUPPORTED does not mean "objectively true." It means the evidence examined supports the claim under the stated assessment method.

---

## 4. Provenance Requirements

Metadata must not impersonate assessment.

**L2 Provenance**:
- If `evidence_support.state` is SUPPORTED, NOT_SUPPORTED, or REFUTED, then `assessed_by` must be a non-empty string.
- If `assessment_method` is set, `assessed_by` must also be set.
- Enforcement: Validation in `AssessedEvidenceState.__post_init__()`.

**L3 Provenance**:
- If `domain_review.status` is REVIEWED, then `reviewed_by` must be a non-empty string.
- NOT_REVIEWED and REQUIRES_REVIEW do not require a reviewer.
- Enforcement: Validation in `AssessedDomainReview.__post_init__()`.

**Failure mode**: Construction with insufficient provenance raises ValueError. The system does not silently accept unproven claims.

---

## 5. Contestation Requirements

Contestation preserves disagreement without claiming resolution.

**Preserve these elements**:
- `challenges`: List of Challenge objects, each containing:
  - `challenge_id`: unique identifier
  - `type`: category (e.g., "gps_position_mismatch")
  - `challenger_source`: who raised it (e.g., "v12_cross_check")
  - `challenged_claim`: what is disputed (descriptive)
  - `counter_evidence`: the contradicting evidence (dict)
  - `method`: how contradiction was found (e.g., "haversine_distance")
  - `created_at`: timestamp
  - `status`: OPEN, CLOSED, UNRESOLVED

**Separate status from resolution**:
- `contestation.status`: UNCONTESTED, CHALLENGED, CONTESTED (state of disagreement)
- `contestation.resolution`: ContestationResolution or None
  - `resolution.status`: UNRESOLVED or RESOLVED (outcome of resolution attempt)
  - `resolution.method`: how it was resolved (if RESOLVED)
  - `resolution.authority`: who decided (future expansion)

**Critical invariant**: CONTESTED with `resolution=None` is valid. It means disagreement is recorded and unresolved by this system.

**What CONTESTED does NOT mean**:
- Does not mean the claim is false
- Does not mean the counter-evidence is true
- Does not automatically resolve to either side being correct

---

## 6. Independence Dimensions

Verifier independence has five orthogonal dimensions:

```python
@dataclass(frozen=True)
class VerifierIndependence:
    implementation: bool  # Different codebase
    method: bool  # Different algorithm or approach
    data: bool  # Different evidence source
    assumption: bool  # Different governing premise
    domain: bool  # Different expertise or validation
```

**Critical invariant**: Each dimension is independent. `implementation=True` does not imply `method=True`, `data=True`, `assumption=True`, or `domain=True`.

Example:
```python
# Valid: two implementations of the same rules (implementation-independent but not method-independent)
VerifierIndependence(
    implementation=True,
    method=False,  # ← same rules, so method is not independent
    data=False,
    assumption=False,
    domain=False
)
```

---

## 7. Backward Compatibility

**Constructor compatibility**:
- `epistemic: EpistemicAssessment | None = None`
- Existing code that creates EvidenceRecord without epistemic continues to work
- No forced migration of existing tests or packages

**Serialization compatibility**:
- Old packages without `epistemic` field remain readable
- The verifier must defensively check `if epistemic is not None` before validation
- Absence of epistemic is not a verification error

**Phase 1 generation**:
- All newly generated packages in Phase 1 MUST populate epistemic with a valid EpistemicAssessment
- Old packages are grandfathered in; new packages have epistemic

---

## 8. Proof Requirements (Falsifiable Tests A–J)

All tests must pass. Existing test suite must run unchanged.

### Test A: L1 does not imply L2
```
L1: PASS
L2: UNVERIFIED (not automatically SUPPORTED)
```

### Test B: L1 does not imply L3
```
L1: PASS
L3: REQUIRES_REVIEW (not automatically REVIEWED or approved)
```

### Test C: SUPPORTED requires provenance
```
AssessedEvidenceState(state=SUPPORTED, assessed_by=None) → ValueError
AssessedEvidenceState(state=SUPPORTED, assessed_by="verifier_v2", assessment_method="...") → Valid
```

### Test D: Contestation status and resolution are orthogonal
```
status: CONTESTED
resolution: None (or resolution.status = UNRESOLVED)
→ Valid: disagreement exists and remains unresolved
```

### Test E: Independence dimensions are independent
```
implementation=True
method=False
→ Valid: can be independent in one dimension without implying others
```

### Test F: Serialization round-trip preserves epistemic exactly
```
object → to_dict() → canonical_json() → json.loads() → EpistemicAssessment
→ Bitwise equivalent
```

### Test G: V11/V12 disagreement generated and preserved
**Critical requirement**: The contestation must be generated from the real execution path, not manually staged.

```python
# Execute real system path
vehicle_snapshot = {...}  # spoofed GPS
independent_snapshot = {...}  # cross-check

v11_result = vehicle_check(request, vehicle_snapshot)
v12_result = vehicle_check(request, independent_snapshot)

# Detect disagreement programmatically
if v11_result["verdict"] != v12_result["verdict"]:
    challenges = [Challenge(...)]  # generated
else:
    challenges = []

# Build epistemic from results
epistemic = EpistemicAssessment(
    contestation=Contestation(
        status=CONTESTED if challenges else UNCONTESTED,
        challenges=challenges
    )
)

# Package and replay
pkg = build_package(...)
pkg_dict = json.loads(canonical_json(pkg))
record_2 = EvidenceRecord(**pkg_dict["record"])

# Verify preservation
assert record_2.epistemic.contestation.status == CONTESTED
assert len(record_2.epistemic.contestation.challenges) > 0
```

The test must NOT:
- Manually construct the expected CONTESTED object
- Assert that a pre-written expected object is what the system produced

The test MUST:
- Run the actual vehicle verification on real (or realistic) inputs
- Detect disagreement from the actual results
- Build epistemic from detected disagreement
- Verify that the package preserves what was detected

### Test H: Computational REFUTED vs Evidentiary REFUTED
```
verification.status = REFUTED (computational layer)
↓
epistemic.evidence_support.state = NOT_SUPPORTED (evidentiary layer)
→ Distinguishable and valid

verification.status = PASS (computational layer)
↓
epistemic.evidence_support.state = REFUTED (evidentiary layer)
→ Distinguishable and valid
```

### Test I: Malformed epistemic fails safely
```
Unknown EvidenceState value → ValueError
Invalid independence field type → ValueError
Missing required provenance → ValueError
Malformed challenge → ValueError

In package: malformed epistemic → verification fails
Authorization NEVER succeeds with malformed epistemic
```

### Test J: Gate semantics unchanged
```
All existing tests in test_gate.py pass unchanged
ALLOW/DEFER/REFUSE decisions unaffected by epistemic layer
```

---

## 9. Critical Test G Requirement (Explicit)

Test G is the experimental control for the Phase 1 claim.

**Test G must demonstrate that the system preserves disagreement generated from real execution.**

The test fails if it:
- Pre-constructs a CONTESTED object and asserts the system produces it
- Manually writes disagreement into the expected output
- Stages a challenge rather than detecting one

The test succeeds if it:
- Exercises the actual vehicle verification on inputs that produce disagreement (V11 vs V12)
- Detects disagreement programmatically from actual results
- Builds epistemic.contestation from detected disagreement
- Packages and replays the record
- Verifies that the preserved contestation matches what was detected

This proves the system itself preserves the disagreement, not that the test author wrote the disagreement into the expected output.

---

## 10. What Phase 1 Does NOT Establish

These claims are explicitly out of scope:

- Truth of observations
- Truth of counter-evidence
- Objective correctness of SUPPORTED state
- Correctness of domain assumptions
- Validity of verification rules
- Sufficiency of evidence merely because EvidenceState exists
- Verifier independence merely from process separation
- Automatic resolution of conflicting evidence
- Human judgment or expert approval
- Safety of an authorized action
- Absence of adversarial manipulation
- That the system knows more in Phase 1 than before

---

## 11. Implementation Checklist

Before declaring Phase 1 complete:

- [ ] Add epistemic.py with all EpistemicAssessment and related dataclasses
- [ ] Add `epistemic: EpistemicAssessment | None = None` field to EvidenceRecord
- [ ] Update EvidenceRecord.__post_init__() to freeze epistemic
- [ ] Update EvidenceRecord.with_updates() to allow epistemic field
- [ ] Update EvidenceRecord.to_dict() to include epistemic
- [ ] Add provenance validation in AssessedEvidenceState.__post_init__()
- [ ] Add provenance validation in AssessedDomainReview.__post_init__()
- [ ] Implement Tests A–J
- [ ] Run full existing suite (no regressions)
- [ ] Generate actual diff and review for correctness
- [ ] Verify Test G uses real execution path
- [ ] Confirm backward compatibility (old packages readable)
- [ ] Confirm new packages populate epistemic

---

## 12. Falsifiability

Phase 1 succeeds if:

1. Existing tests pass unchanged
2. New epistemic structures are properly typed and immutable
3. Test G produces a preserved disagreement artifact from real execution
4. Provenance validation enforces assessment constraints
5. Independence dimensions remain independent
6. Gate authorization semantics are unchanged
7. Serialization round-trip preserves exact structure

Phase 1 fails if:

1. Any existing test breaks
2. Test G manually constructs expected output instead of detecting it
3. Provenance validation is missing or insufficient
4. SUPPORTED can be set without provenance
5. One independence dimension auto-implies another
6. Gate semantics change
7. Serialization loses epistemic information

---

## References

- PHASE_1_SPECIFICATION.md — Full specification with all dataclass definitions
- PHASE_1_AUDIT.md — Repository convention audit and compatibility findings
- docs/BOUNDARIES.md — What the system can and cannot establish (to be created)
