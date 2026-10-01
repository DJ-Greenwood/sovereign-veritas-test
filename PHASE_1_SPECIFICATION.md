# Phase 1: Epistemic Boundaries — Specification

**Status**: Ready to implement. Audit complete. All corrections incorporated.

**Objective**: Make the system distinguish computational verification from evidentiary support and domain review. Do NOT replace Gate semantics. Do NOT automatically solve L2 or L3.

---

## 0. Backward Compatibility and Required-ness

**Critical distinction:**

- `epistemic` field is **optional in the constructor** (no migration of existing code required)
- But **all newly generated Phase-1 packages MUST include `epistemic`**
- Packages without `epistemic` are considered **pre-Phase-1** and remain readable
- The verifier (tools/verify_package.py) must defensively accept packages without epistemic

**Serialization contract:**

- Old packages (no `epistemic` field): remain valid and readable
- New packages (with `epistemic` field): pass full epistemic validation
- Backward-compatible reading: `epistemic` absence is not a verification error
- Forward: all `build_package()` calls in Phase 1 must populate `epistemic` with a valid `EpistemicAssessment`

This preserves the existing test surface while requiring new rigor going forward.

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
         ├── evidence_support: AssessedEvidenceState
         ├── domain_review: AssessedDomainReview
         ├── contestation: Contestation
         └── independence: VerifierIndependence
```

This means:
- Validation at construction time
- Serialization is checked
- Mutation testing is precise
- Schema evolution is intentional

**Implementation guideline**: Follow the repository's existing immutable/dataclass patterns (frozen=True, _freeze/_thaw, _validate_jsonable).

---

## 2. L1 COMPUTATIONAL = PASS: Precise Definition

**What it means:**

> L1 COMPUTATIONAL = PASS means the verification procedure successfully established that the recorded decision is consistent with the specified computation over the recorded inputs.

**What it does NOT mean:**

- The claim is true or corresponds to reality
- The inputs are authentic or trustworthy
- The evidence actually supports the claim
- The measurement is from a real sensor
- The world state matches the recorded state
- An adversary has not manipulated the system
- An action will be safe if authorized based on this

**Formal contract (add to docs/BOUNDARIES.md):**

```
L1 COMPUTATIONAL PASS ≠ TRUTH
L1 COMPUTATIONAL PASS ≠ AUTHENTICITY
L1 COMPUTATIONAL PASS ≠ EVIDENCE_SUPPORT
L1 COMPUTATIONAL PASS = INTERNAL_CONSISTENCY

Verification proves:
  - decision matches gate logic
  - gate logic matches specification
  - inputs are consistent with recorded digests

Verification does NOT prove:
  - inputs came from trustworthy sources
  - claim corresponds to external reality
  - evidence is sufficient for the purpose
  - system is not under adversarial control
```

This definition must be explicit in the codebase, not merely in README.

---

## 3. What Can Set L2 and L3: Provenance Requirement

**The problem:** If arbitrary caller input can simply declare `evidence_support=SUPPORTED`, the field claims what it does not establish.

**Phase 1 solution:** Introduce assessed states that require explicit provenance.

```python
@dataclass(frozen=True)
class AssessedEvidenceState:
    """L2 evidence support with provenance."""
    state: EvidenceState
    assessed_by: str | None = None  # e.g. "verifier-v2", "domain_expert", "cross_check"
    assessment_method: str | None = None  # e.g. "independent_verifier", "contradiction_found"
    assessed_at: str | None = None  # ISO 8601 timestamp
    evidence_dependencies: list[str] = field(default_factory=list)  # what evidence was examined

@dataclass(frozen=True)
class AssessedDomainReview:
    """L3 domain review with provenance."""
    status: DomainReviewStatus
    reviewed_by: str | None = None  # e.g. "system", "domain_expert", "process_X"
    review_method: str | None = None  # e.g. "static_analysis", "expert_judgment"
    reviewed_at: str | None = None  # ISO 8601 timestamp
    assumptions_examined: list[str] = field(default_factory=list)  # which assumptions checked

class EvidenceState(str, Enum):
    """L2: Does evidence support the claim?"""
    UNVERIFIED = "UNVERIFIED"  # ← no assessment yet (default for Phase 1)
    SUPPORTED = "SUPPORTED"  # ← only if assessed_by is set
    NOT_SUPPORTED = "NOT_SUPPORTED"  # ← only if assessed_by is set
    REFUTED = "REFUTED"  # ← evidence contradicts claim; requires assessed_by
    CONTESTED = "CONTESTED"  # ← conflicting assessments; requires challenges
    UNKNOWN = "UNKNOWN"  # ← cannot evaluate
    STALE = "STALE"  # ← expired

class DomainReviewStatus(str, Enum):
    """L3: Are assumptions and rules appropriate?"""
    NOT_REVIEWED = "NOT_REVIEWED"  # ← default for Phase 1
    REVIEWED = "REVIEWED"  # ← reviewed but concerns noted
    REQUIRES_REVIEW = "REQUIRES_REVIEW"  # ← needs expert attention
```

**Invariant**: 
- A state of SUPPORTED, NOT_SUPPORTED, or REFUTED must have `assessed_by` set to a non-empty string
- A CONTESTED state must have non-empty `challenges` list
- UNKNOWN and STALE do not require assessed_by
- UNVERIFIED and NOT_REVIEWED are the defaults when no assessment has occurred

This prevents empty claims while allowing future expansion of assessment sources.

---

## 4. Contestation: Preserve Identity and Evidence Dependency

**Current structure:**

```python
@dataclass(frozen=True)
class Contestation:
    status: ContestationStatus
    challenges: list[Challenge] = field(default_factory=list)
    resolution: ContestationResolution | None = None

@dataclass(frozen=True)
class Challenge:
    type: str  # e.g. "gps_spoofing", "evidence_contradiction"
    evidence: dict[str, Any]  # counter-evidence
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

**Extend to preserve accountability:**

```python
@dataclass(frozen=True)
class Challenge:
    challenge_id: str  # unique identifier
    type: str  # e.g. "gps_spoofing", "evidence_contradiction", "assumption_violation"
    challenger_source: str  # who raised it: "cross_check", "verifier_v2", "external_report"
    challenged_claim: str  # what is being disputed (descriptive)
    counter_evidence: dict[str, Any]  # the contradicting evidence
    method: str | None = None  # how the contradiction was found (e.g. "distance_calculation", "source_disagreement")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "OPEN"  # OPEN, CLOSED, UNRESOLVED
```

**Why this matters:**

A CONTESTED flag alone tells the reader nothing about what is contested or by whom.

With identity:
```json
{
  "contestation": {
    "status": "CONTESTED",
    "challenges": [
      {
        "challenge_id": "ch-001",
        "type": "gps_position_mismatch",
        "challenger_source": "v12_cross_check",
        "challenged_claim": "vehicle is at GPS position (40.71, -74.00)",
        "counter_evidence": {
          "independent_position": "(40.72, -74.01)",
          "disagreement_m": 111
        },
        "method": "haversine_distance",
        "created_at": "2026-10-01T03:22:15Z"
      }
    ],
    "resolution": null
  }
}
```

Now the reader knows:
- What is contested (specific claim)
- Who raised it (cross_check system)
- What evidence contradicts it (independent position)
- How the contradiction was found (distance calculation)

---

## 5. Separation of Contestation Status and Resolution

**Contestation status** (state of disagreement):
```python
class ContestationStatus(str, Enum):
    UNCONTESTED = "UNCONTESTED"  # ← no conflict recorded
    CHALLENGED = "CHALLENGED"  # ← challenge submitted, not yet full conflict
    CONTESTED = "CONTESTED"  # ← conflicting evidence recorded
```

**Resolution status** (outcome of attempt to resolve):
```python
@dataclass(frozen=True)
class ContestationResolution:
    status: ResolutionStatus
    method: str | None = None  # e.g. "independent_method", "domain_expert"
    authority: str | None = None  # who decided (future expansion)
    resolved_at: str | None = None  # when it was resolved

class ResolutionStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"  # ← no resolution attempt or no decision
    RESOLVED = "RESOLVED"  # ← has resolution (but not necessarily "true")
```

**Key invariant:**

`CONTESTED` with `resolution=None` (or `resolution.status=UNRESOLVED`) is **valid and expected** in Phase 1.

It means: "Disagreement exists. This system has not resolved it. Domain authority or next layer must decide."

---

## 6. Complete Type Structure

```python
@dataclass(frozen=True)
class EpistemicAssessment:
    """Epistemic context for a decision, separate from authorization."""
    computational: ComputationalVerification
    evidence_support: AssessedEvidenceState
    domain_review: AssessedDomainReview
    contestation: Contestation
    independence: VerifierIndependence

@dataclass(frozen=True)
class ComputationalVerification:
    """L1: Did the computation execute as specified?"""
    status: str  # "PASS", "FAIL", "REFUTED", etc. (from VerificationStatus)

class EvidenceState(str, Enum):
    """L2: Does evidence support the claim?"""
    UNVERIFIED = "UNVERIFIED"
    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    REFUTED = "REFUTED"  # ← evidence contradicts claim (distinct from computational REFUTED)
    CONTESTED = "CONTESTED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"

@dataclass(frozen=True)
class AssessedEvidenceState:
    """L2 with provenance."""
    state: EvidenceState
    assessed_by: str | None = None
    assessment_method: str | None = None
    assessed_at: str | None = None
    evidence_dependencies: list[str] = field(default_factory=list)

class DomainReviewStatus(str, Enum):
    """L3: Are assumptions and rules appropriate?"""
    NOT_REVIEWED = "NOT_REVIEWED"
    REVIEWED = "REVIEWED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"

@dataclass(frozen=True)
class AssessedDomainReview:
    """L3 with provenance."""
    status: DomainReviewStatus
    reviewed_by: str | None = None
    review_method: str | None = None
    reviewed_at: str | None = None
    assumptions_examined: list[str] = field(default_factory=list)

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
    challenge_id: str
    type: str
    challenger_source: str
    challenged_claim: str
    counter_evidence: dict[str, Any]
    method: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "OPEN"

@dataclass(frozen=True)
class ContestationResolution:
    status: ResolutionStatus
    method: str | None = None
    authority: str | None = None
    resolved_at: str | None = None

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
    epistemic: EpistemicAssessment | None = None  # ← NEW, optional
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

**Backward compatibility:**

- `epistemic=None` is valid (represents pre-Phase-1 records or those without assessment)
- Existing constructor calls without `epistemic` continue to work
- Existing packages without `epistemic` remain readable

---

## 8. Serialization and Replay

**Requirements:**

1. `EpistemicAssessment` and all nested objects serialize to canonical JSON
2. Deserialization from a package produces the exact same object
3. Tampering with epistemic fields is detectable (hash chain coverage)
4. Verifier can accept packages without `epistemic` (backward-compatible)

**Implementation:**

- Follow existing `_freeze()` / `_thaw()` patterns
- `canonical_json()` must handle nested dataclasses (convert to dicts)
- `package_digest()` includes epistemic in the hash
- Verifier must validate epistemic objects if present, accept omission if absent

---

## 9. Required Tests (Revised Set)

### Test A: L1 does not imply L2

```python
def test_l1_pass_does_not_imply_l2_supported():
    """L1 PASS must not automatically mean evidence is SUPPORTED."""
    rec = EvidenceRecord(
        record_id="a",
        input_digest="abc",
        verification={"status": "PASS"},
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=AssessedEvidenceState(
                state=EvidenceState.UNVERIFIED  # ← no automatic support
            ),
            domain_review=AssessedDomainReview(status=DomainReviewStatus.NOT_REVIEWED),
            contestation=Contestation(status=ContestationStatus.UNCONTESTED),
            independence=VerifierIndependence(False, False, False, False, False)
        )
    )
    assert rec.verification["status"] == "PASS"
    assert rec.epistemic.evidence_support.state == EvidenceState.UNVERIFIED
```

### Test B: L1 does not imply L3

```python
def test_l1_pass_does_not_imply_l3_approved():
    """L1 PASS must not automatically mean domain is REVIEWED/APPROVED."""
    rec = EvidenceRecord(
        record_id="b",
        input_digest="abc",
        verification={"status": "PASS"},
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=AssessedEvidenceState(state=EvidenceState.SUPPORTED),
            domain_review=AssessedDomainReview(
                status=DomainReviewStatus.REQUIRES_REVIEW  # ← explicit, not automatic
            ),
            contestation=Contestation(status=ContestationStatus.UNCONTESTED),
            independence=VerifierIndependence(True, False, False, False, False)
        )
    )
    assert rec.epistemic.domain_review.status == DomainReviewStatus.REQUIRES_REVIEW
```

### Test C: SUPPORTED requires assessed_by

```python
def test_evidence_support_requires_provenance():
    """SUPPORTED state must have assessed_by and assessment_method."""
    # Invalid: no provenance
    with pytest.raises(ValueError):
        AssessedEvidenceState(
            state=EvidenceState.SUPPORTED,
            assessed_by=None,  # ← error: empty string for SUPPORTED
            assessment_method=None
        )
    
    # Valid: with provenance
    valid = AssessedEvidenceState(
        state=EvidenceState.SUPPORTED,
        assessed_by="cross_check_v2",
        assessment_method="independent_verifier"
    )
    assert valid.assessed_by is not None
```

### Test D: Contestation status and resolution are orthogonal

```python
def test_contested_with_unresolved_is_valid():
    """CONTESTED with UNRESOLVED resolution is valid."""
    cont = Contestation(
        status=ContestationStatus.CONTESTED,
        challenges=[
            Challenge(
                challenge_id="ch-001",
                type="gps_mismatch",
                challenger_source="v12_cross_check",
                challenged_claim="vehicle position",
                counter_evidence={"independent": "(40.72, -74.01)"},
                method="haversine"
            )
        ],
        resolution=None  # ← or ContestationResolution(status=ResolutionStatus.UNRESOLVED)
    )
    
    assert cont.status == ContestationStatus.CONTESTED
    # This DOES NOT imply resolution
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
    assert ind_a.method != ind_b.method  # ← independently specifiable
```

### Test F: Epistemic survives serialization and mutation

```python
def test_epistemic_serialization_and_detection():
    """Epistemic data survives round-trip and mutation is detected."""
    rec = EvidenceRecord(
        record_id="f",
        input_digest="abc",
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=AssessedEvidenceState(
                state=EvidenceState.CONTESTED,
                assessed_by="cross_check_v2"
            ),
            domain_review=AssessedDomainReview(status=DomainReviewStatus.REQUIRES_REVIEW),
            contestation=Contestation(
                status=ContestationStatus.CONTESTED,
                challenges=[Challenge(
                    challenge_id="ch-001",
                    type="position_mismatch",
                    challenger_source="v12",
                    challenged_claim="gps_position",
                    counter_evidence={"alt_pos": "..."}
                )]
            ),
            independence=VerifierIndependence(True, False, True, False, False)
        )
    )
    
    # Serialize
    serialized = canonical_json(rec.to_dict())
    
    # Deserialize
    deserialized = json.loads(serialized)
    rec2 = EvidenceRecord(**deserialized)
    
    # Must match exactly
    assert rec.epistemic.contestation.challenges[0].challenge_id == rec2.epistemic.contestation.challenges[0].challenge_id
    
    # Tampering is detected
    deserialized["epistemic"]["contestation"]["challenges"][0]["type"] = "TAMPERED"
    assert serialize_and_verify(deserialized) fails
```

### Test G: V11/V12 information preservation

```python
def test_v11_v12_preserves_conflicting_evidence():
    """V11/V12 case: authorization unchanged, but evidence conflict is recorded."""
    
    # V11: without independent check
    pkg_v11 = make_vehicle_package(scenario="spoofed", cross_check=False)
    assert pkg_v11["decision"]["decision"] == "ALLOW"
    assert pkg_v11["epistemic"]["contestation"]["status"] == "UNCONTESTED"
    assert len(pkg_v11["epistemic"]["contestation"]["challenges"]) == 0
    
    # V12: with independent check
    pkg_v12 = make_vehicle_package(scenario="spoofed", cross_check=True)
    assert pkg_v12["decision"]["decision"] == "REFUSE"  # ← same as before
    
    # But NOW the conflict is recorded
    assert pkg_v12["epistemic"]["contestation"]["status"] == "CONTESTED"
    assert len(pkg_v12["epistemic"]["contestation"]["challenges"]) > 0
    
    # Challenge preserves the specifics
    challenge = pkg_v12["epistemic"]["contestation"]["challenges"][0]
    assert challenge["type"] == "gps_position_mismatch"
    assert challenge["challenger_source"] == "v12_cross_check"
    assert challenge["counter_evidence"]["disagreement_m"] == 111  # from existing test
    
    # Resolution is unresolved (system cannot decide)
    assert pkg_v12["epistemic"]["contestation"]["resolution"] is None or \
           pkg_v12["epistemic"]["contestation"]["resolution"]["status"] == "UNRESOLVED"
    
    # Semantic improvement: old representation would discard the evidence conflict
    # new representation preserves it for auditing/escalation
```

### Test H: Computational REFUTED vs Evidentiary REFUTED

```python
def test_computational_refuted_independent_from_evidentiary_refuted():
    """verification.REFUTED and epistemic.REFUTED are distinct."""
    
    # Case 1: Verifier concluded prediction is false (computational)
    rec_comp_refuted = EvidenceRecord(
        record_id="comp",
        input_digest="abc",
        verification={"status": "REFUTED"},  # ← computational
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="REFUTED"),
            evidence_support=AssessedEvidenceState(
                state=EvidenceState.CONTESTED  # ← but evidence is uncertain
            ),
            domain_review=AssessedDomainReview(status=DomainReviewStatus.NOT_REVIEWED),
            contestation=Contestation(status=ContestationStatus.CONTESTED),
            independence=VerifierIndependence(True, False, False, False, False)
        )
    )
    
    # Case 2: Verifier passed, but evidence contradicts (evidentiary)
    rec_evid_refuted = EvidenceRecord(
        record_id="evid",
        input_digest="abc",
        verification={"status": "PASS"},  # ← computational passed
        epistemic=EpistemicAssessment(
            computational=ComputationalVerification(status="PASS"),
            evidence_support=AssessedEvidenceState(
                state=EvidenceState.REFUTED,  # ← evidence contradicts (different layer)
                assessed_by="cross_check_v2"
            ),
            domain_review=AssessedDomainReview(status=DomainReviewStatus.NOT_REVIEWED),
            contestation=Contestation(status=ContestationStatus.CONTESTED),
            independence=VerifierIndependence(True, False, True, False, False)
        )
    )
    
    # These are completely distinguishable
    assert rec_comp_refuted.verification["status"] == "REFUTED"
    assert rec_comp_refuted.epistemic.computational.status == "REFUTED"
    assert rec_comp_refuted.epistemic.evidence_support.state != EvidenceState.REFUTED
    
    assert rec_evid_refuted.verification["status"] == "PASS"
    assert rec_evid_refuted.epistemic.computational.status == "PASS"
    assert rec_evid_refuted.epistemic.evidence_support.state == EvidenceState.REFUTED
    
    # Serialization produces different objects
    assert canonical_json(rec_comp_refuted.to_dict()) != canonical_json(rec_evid_refuted.to_dict())
```

### Test I: Malformed epistemic fails safely

```python
def test_malformed_epistemic_fails_closed():
    """Unknown states, invalid values, missing fields fail safely."""
    
    # Unknown EvidenceState
    with pytest.raises(ValueError):
        AssessedEvidenceState(state="FABRICATED")
    
    # Unknown ContestationStatus
    with pytest.raises(ValueError):
        Contestation(status="MADE_UP")
    
    # Invalid independence value
    with pytest.raises(ValueError):
        VerifierIndependence("yes", False, False, False, False)  # ← not bool
    
    # In a package, malformed epistemic should cause verification to reject
    pkg = make_valid_package()
    pkg["epistemic"]["evidence_support"]["state"] = "UNKNOWN_STATE"
    
    # Verifier rejects this
    assert verify_package(pkg) fails
```

### Test J: Existing Gate behavior unchanged

```python
def test_gate_decisions_unchanged():
    """All existing Gate tests must pass without modification."""
    # Run the entire existing test_gate.py suite
    # Every assertion on ALLOW, DEFER, REFUSE must remain unchanged
```

---

## 10. What Phase 1 Does NOT Establish

**Phase 1 does NOT establish:**

- Truth of observations
- Authenticity of real-world sensors or data sources
- Correctness of domain assumptions
- Sufficiency of evidence merely because an EvidenceState exists
- Independence merely because a verifier uses another implementation
- Resolution of conflicting evidence (only preservation)
- Human judgment or expert approval
- Safety of an authorized action
- Absence of adversarial manipulation
- Consciousness, intelligence, or agency of any system component
- That a claim is justified beyond the scope of the recorded assessment

**These are deliberately left to external processes** (domain experts, operators, regulatory oversight).

---

## 11. Success Criteria Checklist

**Phase 1 is complete when:**

- [ ] Gate ALLOW/DEFER/REFUSE unchanged
- [ ] Existing tests (test_gate.py, test_package.py) remain green
- [ ] EpistemicAssessment is typed and immutable
- [ ] L1/L2/L3 are explicitly separated
- [ ] L1 PASS cannot imply L2 SUPPORTED (Test A)
- [ ] L1 PASS cannot imply L3 REVIEWED (Test B)
- [ ] SUPPORTED requires assessed_by (Test C)
- [ ] Contestation status and resolution are orthogonal (Test D)
- [ ] Independence dimensions are independent (Test E)
- [ ] Epistemic survives serialization/replay (Test F)
- [ ] Tampering with epistemic is detectable in package hash
- [ ] V11/V12 demonstrates information preservation (Test G)
- [ ] Computational REFUTED and evidentiary REFUTED coexist (Test H)
- [ ] Malformed epistemic objects fail safely (Test I)
- [ ] No automatic truth inference
- [ ] No automatic conflict resolution
- [ ] No new trust/confidence scores
- [ ] No broad kernel refactor
- [ ] Backward-compatible reading of pre-Phase-1 packages
- [ ] All newly generated packages include epistemic

---

## 12. What Phase 1 Does NOT Do

- Automatically resolve disputes (L2 and L3 remain human/expert responsibilities)
- Add confidence or trust scores
- Modify the Gate contract
- Replace ALLOW/DEFER/REFUSE
- Add an LLM or external resolver
- Create a new database
- Perform broad refactoring
- Infer truth from disagreement
- Establish safety
- Claim independence beyond what is explicitly measured

---

## 13. After Phase 1

With these structures in place, future work can:

- Implement explicit L2 and L3 verification hooks with provenance tracking
- Add domain-expert decision records
- Extend `ContestationResolution` with authority/method tracking and formal resolution
- Query "how many packages have unresolved contestations?"
- Build tooling that audits the epistemic surface of a corpus
- Route contested decisions to external oversight systems
- Implement escalation workflows based on unresolved challenges

But Phase 1 creates the **semantic foundation** without claiming to solve governance.

---

## 14. Acceptance Criteria

Do not proceed to implementation until:

1. This specification has been reviewed and approved
2. All 10 test categories (A–J) are understood
3. Backward compatibility strategy is confirmed
4. Provenance requirements for assessed states are clear
5. Integration with existing serialization machinery is confirmed

**Next step:** Review this specification. Once approved, implement Phase 1.
