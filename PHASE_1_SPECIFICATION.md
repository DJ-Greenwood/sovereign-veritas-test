# Phase 1: Epistemic Boundaries — Specification

**Status**: Ready to implement. Audit complete. Corrections incorporated.

**Objective**: Make the system distinguish computational verification from evidentiary support and domain review. Do NOT replace Gate semantics. Do NOT automatically solve L2 or L3.

---

## 1. Core Design Principle: Typed, Not Free-Form

The epistemic layer must be a **typed immutable structure**, not `dict[str, Any]`.

**Incorrect**:
```python
EvidenceRecord
    └── epistemic: dict[str, Any]  # ← internal structs, no schema
```

**Correct**:
```python
EvidenceRecord
    └── epistemic: EpistemicAssessment | None  # ← fully typed
         ├── computational: ComputationalVerification
         ├── evidence_support: EvidenceState
         ├── domain_review: DomainReviewStatus
         ├── contestation: ContestationRecord
         └── independence: VerifierIndependence
```

This means:
- Validation at construction time
- Serialization is checked
- Mutation testing is precise
- Schema evolution is intentional

**Implementation guideline**: Follow the repository's existing immutable/dataclass patterns (frozen=True, _freeze/_thaw, _validate_jsonable).

---

## 2. Critical: Resolve the REFUTED Naming Collision

**The problem the audit found:**

The repository already uses `VerificationStatus.REFUTED` to mean "the verifier concluded the prediction is false."

Adding `epistemic.evidence_support = REFUTED` creates semantic ambiguity:
- Does it mean the same thing?
- Does it mean something different?

**The solution:**

Keep both, but make them **independently representable and tested**.

```python
# Computational layer (existing)
VerificationStatus
    ├── PASS
    ├── FAIL
    ├── REFUTED  # ← verifier concluded prediction is false
    ├── INSUFFICIENT_EVIDENCE
    ├── NOT_VERIFIED
    └── UNKNOWN

# Epistemic layer (new)
EvidenceState
    ├── SUPPORTED  # ← evidence backs the claim
    ├── NOT_SUPPORTED  # ← no evidence either way
    ├── REFUTED  # ← evidence contradicts the claim (different meaning)
    ├── CONTESTED  # ← conflicting evidence recorded
    ├── UNKNOWN  # ← evidence exists but cannot be evaluated
    └── STALE  # ← evidence was valid but expired
```

**Required test** (Test 8 in the test plan):

```python
def test_computational_refuted_independent_from_evidentiary_refuted():
    """Prove that verification.REFUTED and epistemic.REFUTED are distinct concepts."""
    
    # Case A: Verifier says prediction is false
    # but evidence sources don't explicitly contradict each other
    record_a = EvidenceRecord(
        verification={"status": "REFUTED"},  # computational
        epistemic=EpistemicAssessment(
            evidence_support=EvidenceState.NOT_SUPPORTED  # different layer
        )
    )
    
    # Case B: Verifier says prediction is true (PASS)
    # but two evidence sources directly contradict
    record_b = EvidenceRecord(
        verification={"status": "PASS"},  # computational passes
        epistemic=EpistemicAssessment(
            evidence_support=EvidenceState.REFUTED  # but evidence contradicts
        )
    )
    
    # These must serialize and verify differently
    assert serialize(record_a) != serialize(record_b)
    assert verify(record_a) != verify(record_b)
```

This proves the distinction is real and testable.

---

## 3. Contestation: Separate Status from Resolution

**The problem the correction found:**

This sequence:
```
UNCONTESTED → CHALLENGED → CONTESTED → RESOLVED → UNRESOLVED
```

mixes "what is the state of disagreement?" with "has it been resolved?"

**The solution:**

Keep them as separate dimensions:

```python
@dataclass(frozen=True)
class Contestation:
    status: ContestationStatus  # UNCONTESTED, CHALLENGED, CONTESTED
    challenges: list[Challenge] = field(default_factory=list)  # what was challenged
    resolution: ContestationResolution | None = None  # how/whether it was addressed

@dataclass(frozen=True)
class ContestationResolution:
    status: ResolutionStatus  # UNRESOLVED, RESOLVED
    method: str | None = None  # e.g. "independent_method", "domain_expert", "both_valid"
    authority: str | None = None  # who decided (future expansion)
    evidence: dict[str, Any] | None = None  # supporting evidence for the resolution (future)

class ContestationStatus(str, Enum):
    UNCONTESTED = "UNCONTESTED"  # no challenge recorded
    CHALLENGED = "CHALLENGED"  # challenge submitted, evidence pending
    CONTESTED = "CONTESTED"  # conflicting evidence recorded

class ResolutionStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"  # remains unresolved
    RESOLVED = "RESOLVED"  # has resolution (but not necessarily "true")
```

**Key invariant:**

`CONTESTED` with `resolution=None` is valid.

It means: "Disagreement exists and remains unresolved by this system."

This is honest and prevents false resolution.

---

## 4. Verification Independence: Exact Dimensions

```python
@dataclass(frozen=True)
class VerifierIndependence:
    implementation: bool  # Different codebase
    method: bool  # Different algorithm or approach
    data: bool  # Different evidence source
    assumption: bool  # Different governing premise
    domain: bool  # Different expertise or validation
```

**Critical invariant:**

`implementation=True` must NOT automatically imply any other dimension is True.

**Required test** (Test 5 in the test plan):

```python
def test_implementation_independence_does_not_imply_method_independence():
    """Prove independence dimensions are truly independent."""
    
    # Two verifiers, different code, same rules
    ind = VerifierIndependence(
        implementation=True,   # ← true
        method=False,          # ← but not this
        data=False,
        assumption=False,
        domain=False
    )
    
    # Must be representable and testable
    pkg = build_package(..., independence=ind)
    assert pkg["verifier"]["independence"]["implementation"] is True
    assert pkg["verifier"]["independence"]["method"] is False
    
    # Verifier cannot claim method independence if it implements the same rules
    assert not all([ind.method, ind.data, ind.assumption, ind.domain])
```

---

## 5. Authorization Policy Remains Explicit

Keep the existing Gate contract. Add an optional `authorization_policy` field to clarify which L-levels were checked:

```python
@dataclass(frozen=True)
class Authorization:
    decision: str  # "ALLOW", "DEFER", "REFUSE" (unchanged)
    policy: AuthorizationPolicy  # L1_ONLY, L1_AND_L2, L1_AND_L2_AND_L3, etc.

class AuthorizationPolicy(str, Enum):
    L1_ONLY = "L1_ONLY"
    L1_AND_L2 = "L1_AND_L2"  # hypothetical future policy
    L1_AND_L2_AND_L3 = "L1_AND_L2_AND_L3"  # hypothetical future policy
```

**Invariant:**

The current Gate always uses `L1_ONLY` (it only verifies computation).

Making this explicit prevents future confusion.

---

## 6. Complete Type Structure

```python
@dataclass(frozen=True)
class EpistemicAssessment:
    """Epistemic context for a decision, separate from authorization."""
    
    computational: ComputationalVerification
    evidence_support: EvidenceState
    domain_review: DomainReviewStatus
    contestation: Contestation
    independence: VerifierIndependence

@dataclass(frozen=True)
class ComputationalVerification:
    """L1: Did the computation execute as specified?"""
    status: str  # "PASS", "FAIL", "REFUTED", etc. (from VerificationStatus)
    confidence: float | None = None  # optional; not yet used

class EvidenceState(str, Enum):
    """L2: Does evidence support the claim?"""
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    REFUTED = "REFUTED"  # ← different from verification.REFUTED
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"

class DomainReviewStatus(str, Enum):
    """L3: Are assumptions and rules appropriate?"""
    APPROVED = "APPROVED"  # ← domain expert/authority has approved
    NOT_REVIEWED = "NOT_REVIEWED"  # ← no review yet
    REQUIRES_REVIEW = "REQUIRES_REVIEW"  # ← needs expert attention
    REJECTED = "REJECTED"  # ← domain expert has objected

@dataclass(frozen=True)
class Contestation:
    status: ContestationStatus
    challenges: list[Challenge] = field(default_factory=list)
    resolution: ContestationResolution | None = None

class ContestationStatus(str, Enum):
    UNCONTESTED = "UNCONTESTED"
    CHALLENGED = "CHALLENGED"
    CONTESTED = "CONTESTED"

@dataclass(frozen=True)
class Challenge:
    type: str  # e.g. "gps_spoofing", "evidence_contradiction"
    evidence: dict[str, Any]  # counter-evidence
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass(frozen=True)
class ContestationResolution:
    status: ResolutionStatus
    method: str | None = None
    authority: str | None = None

class ResolutionStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"

@dataclass(frozen=True)
class VerifierIndependence:
    implementation: bool
    method: bool
    data: bool
    assumption: bool
    domain: bool
```

---

## 7. Integration: Add to EvidenceRecord

```python
@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    input_digest: str
    prediction: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    epistemic: EpistemicAssessment | None = None  # ← NEW
    capability: str | None = None
    action: dict[str, Any] | None = None
    decision: str | None = None
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, Any] | None = None
    evidence_quality: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_digest: str | None = None
```

**Important**: `epistemic` is optional. Existing code continues to work.

---

## 8. Serialization and Validation

Follow existing patterns:

- `__post_init__` validates `epistemic` is JSON-serializable (use existing `_validate_jsonable()`)
- `with_updates()` adds `"epistemic"` to allowed fields
- `to_dict()` includes epistemic (as dict if not None)
- `_freeze()` and `_thaw()` handle nested dataclasses

Example:

```python
def __post_init__(self) -> None:
    # existing code...
    epistemic = _freeze(self.epistemic)
    _validate_jsonable(epistemic, "epistemic")
    object.__setattr__(self, "epistemic", epistemic)
```

---

## 9. Required Tests (Minimal Set)

All tests should pass without modifying existing Gate behavior.

### Test A: L1 does not imply L2

```python
def test_l1_pass_does_not_imply_l2_supported():
    """L1 computational PASS must not automatically mean evidence is SUPPORTED."""
    rec = EvidenceRecord(
        record_id="a",
        input_digest="abc",
        verification={"status": "PASS"},
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=EvidenceState.UNVERIFIED,  # ← not automatic
            domain_review=DomainReviewStatus.NOT_REVIEWED,
            contestation=Contestation(status=ContestationStatus.UNCONTESTED),
            independence=VerifierIndependence(False, False, False, False, False)
        )
    )
    assert rec.verification["status"] == "PASS"
    assert rec.epistemic.evidence_support == EvidenceState.UNVERIFIED
```

### Test B: L1 does not imply L3

```python
def test_l1_pass_does_not_imply_l3_approved():
    """L1 computational PASS must not automatically mean domain is APPROVED."""
    rec = EvidenceRecord(
        record_id="b",
        input_digest="abc",
        verification={"status": "PASS"},
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=EvidenceState.SUPPORTED,
            domain_review=DomainReviewStatus.REQUIRES_REVIEW,  # ← explicit
            contestation=Contestation(status=ContestationStatus.UNCONTESTED),
            independence=VerifierIndependence(True, False, False, False, False)
        )
    )
    assert rec.epistemic.domain_review == DomainReviewStatus.REQUIRES_REVIEW
```

### Test C: Authorization policy is distinguishable

```python
def test_authorization_policy_l1_only_vs_l1_l2_l3():
    """L1_ONLY and L1_L2_L3 policies must be distinguishable."""
    # Current: implicitly L1_ONLY
    decision_a = Decision("ALLOW")
    
    # Future: could explicitly be L1_AND_L2_AND_L3
    # (represented in package, not in Decision itself)
    pkg_a = build_package(..., authorization_policy=AuthorizationPolicy.L1_ONLY)
    pkg_b = build_package(..., authorization_policy=AuthorizationPolicy.L1_AND_L2_AND_L3)
    
    assert pkg_a["authorization"]["policy"] == "L1_ONLY"
    assert pkg_b["authorization"]["policy"] == "L1_AND_L2_AND_L3"
```

### Test D: CONTESTED does not imply REFUTED

```python
def test_contested_does_not_mean_refuted():
    """CONTESTED means disagreement exists, not that one side is false."""
    rec = EvidenceRecord(
        record_id="d",
        input_digest="abc",
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=EvidenceState.CONTESTED,  # ← disagreement
            domain_review=DomainReviewStatus.REQUIRES_REVIEW,
            contestation=Contestation(
                status=ContestationStatus.CONTESTED,
                resolution=None  # ← unresolved
            ),
            independence=VerifierIndependence(True, False, True, False, False)
        )
    )
    
    # CONTESTED is not the same as REFUTED
    assert rec.epistemic.contestation.status == ContestationStatus.CONTESTED
    assert rec.epistemic.contestation.resolution is None  # not resolved
```

### Test E: Independence dimensions are independent

```python
def test_implementation_independence_independent_of_method():
    """implementation=True must not imply method=True."""
    ind_a = VerifierIndependence(
        implementation=True,
        method=False,
        data=False,
        assumption=False,
        domain=False
    )
    ind_b = VerifierIndependence(
        implementation=True,
        method=True,
        data=False,
        assumption=False,
        domain=False
    )
    
    assert ind_a.implementation == ind_b.implementation
    assert ind_a.method != ind_b.method  # ← independent
```

### Test F: V11/V12 preserves conflicting evidence

```python
def test_v11_v12_with_contested_status():
    """V11/V12 vehicle geofence case: can preserve evidence conflict in package."""
    # V11: GPS says vehicle is inside, spoofed
    # Without independent check: ALLOW
    pkg_v11 = make_vehicle_package(scenario="spoofed", cross_check=False)
    assert pkg_v11["decision"]["decision"] == "ALLOW"
    assert pkg_v11["epistemic"]["contestation"]["status"] == "UNCONTESTED"  # no conflict detected
    
    # V12: With independent position check
    # Conflict detected: REFUSE + CONTESTED
    pkg_v12 = make_vehicle_package(scenario="spoofed", cross_check=True)
    assert pkg_v12["decision"]["decision"] == "REFUSE"
    assert pkg_v12["epistemic"]["contestation"]["status"] == "CONTESTED"
    assert pkg_v12["epistemic"]["contestation"]["resolution"] is None  # unresolved
    assert len(pkg_v12["epistemic"]["contestation"]["challenges"]) > 0
```

### Test G: Existing Gate behavior unchanged

```python
def test_gate_decisions_unchanged():
    """All existing Gate tests must pass without modification."""
    # Run all of tests/test_gate.py
    # All assertions remain: ALLOW, DEFER, REFUSE as before
```

### Test H: Computational REFUTED vs Evidentiary REFUTED

```python
def test_computational_refuted_independent_from_evidentiary_refuted():
    """verification.REFUTED and epistemic.REFUTED are distinct concepts."""
    
    # Verifier concluded prediction is false (computational)
    rec_comp_refuted = EvidenceRecord(
        record_id="comp",
        input_digest="abc",
        verification={"status": "REFUTED"},  # ← computational layer
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="REFUTED"),
            evidence_support=EvidenceState.CONTESTED,  # ← evidence level: uncertain
            domain_review=DomainReviewStatus.NOT_REVIEWED,
            contestation=Contestation(status=ContestationStatus.CONTESTED),
            independence=VerifierIndependence(True, False, False, False, False)
        )
    )
    
    # Evidence contradicts the claim (evidentiary)
    rec_evid_refuted = EvidenceRecord(
        record_id="evid",
        input_digest="abc",
        verification={"status": "PASS"},  # ← computational: passed
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=EvidenceState.REFUTED,  # ← evidentiary: contradicted
            domain_review=DomainReviewStatus.NOT_REVIEWED,
            contestation=Contestation(status=ContestationStatus.CONTESTED),
            independence=VerifierIndependence(True, False, True, False, False)
        )
    )
    
    # These must be distinguishable
    assert rec_comp_refuted.verification["status"] == "REFUTED"
    assert rec_comp_refuted.epistemic.evidence_support != EvidenceState.REFUTED
    
    assert rec_evid_refuted.verification["status"] == "PASS"
    assert rec_evid_refuted.epistemic.evidence_support == EvidenceState.REFUTED
```

---

## 10. Success Criteria

**Phase 1 is complete when:**

1. ✓ `EpistemicAssessment` is a typed, immutable dataclass (not `dict[str, Any]`)
2. ✓ `EvidenceRecord` has optional `epistemic: EpistemicAssessment | None` field
3. ✓ All 8 tests (A–H) pass
4. ✓ All existing `test_gate.py` and `test_package.py` tests pass unchanged
5. ✓ Gate authorization logic is completely unchanged (ALLOW/DEFER/REFUSE as before)
6. ✓ Verification dependency is inverted: the verifier understands epistemic fields but doesn't require them
7. ✓ V11/V12 vehicle case now preserves conflicting evidence in the package without changing the decision mechanism

**Phase 1 is NOT complete if:**

- Gate semantics change
- Existing tests break
- `epistemic` is forced as required (must be optional)
- A dict is used instead of a typed structure
- Computational REFUTED and evidentiary REFUTED cannot be simultaneously represented
- The package leaks implementation details (dataclass internals in JSON)

---

## 11. What Phase 1 Does NOT Do

- Automatically resolve disputes (L2 and L3 remain human responsibilities)
- Add confidence or trust scores
- Modify the Gate contract
- Replace ALLOW/DEFER/REFUSE
- Add an LLM or external resolver
- Create a new database
- Perform broad refactoring
- Infer truth from disagreement

---

## 12. After Phase 1

With these structures in place, future work can:

- Implement explicit L2 and L3 verification hooks
- Add domain-expert decision records
- Extend `ContestationResolution` with authority/method tracking
- Query "how many packages have unresolved contestations?"
- Build tooling that audits the epistemic surface of a corpus

But Phase 1 creates the **semantic foundation** without claiming to solve governance.

---

**Next step:** Implement the Phase 1 specification as written above, passing all 8 tests.
