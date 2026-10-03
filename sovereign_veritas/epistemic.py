"""Epistemic assessment layer for evidence records.

Separates L1 computational verification from L2 evidentiary support and L3 domain review.
All structures are immutable and JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime, timezone


class EvidenceState(str, Enum):
    """L2: Does evidence support the claim?"""
    UNVERIFIED = "UNVERIFIED"  # ← no assessment yet (default for Phase 1)
    SUPPORTED = "SUPPORTED"  # ← only if assessed_by is set
    NOT_SUPPORTED = "NOT_SUPPORTED"  # ← only if assessed_by is set
    REFUTED = "REFUTED"  # ← evidence contradicts claim; distinct from computational REFUTED
    CONTESTED = "CONTESTED"  # ← conflicting assessments; requires challenges
    UNKNOWN = "UNKNOWN"  # ← cannot evaluate
    STALE = "STALE"  # ← expired


class DomainReviewStatus(str, Enum):
    """L3: Are assumptions and rules appropriate?"""
    NOT_REVIEWED = "NOT_REVIEWED"  # ← default for Phase 1
    REVIEWED = "REVIEWED"  # ← reviewed but concerns noted
    REQUIRES_REVIEW = "REQUIRES_REVIEW"  # ← needs expert attention


class ContestationStatus(str, Enum):
    """State of disagreement."""
    UNCONTESTED = "UNCONTESTED"  # ← no conflict recorded
    CHALLENGED = "CHALLENGED"  # ← challenge submitted, not yet full conflict
    CONTESTED = "CONTESTED"  # ← conflicting evidence recorded


class ResolutionStatus(str, Enum):
    """Outcome of attempt to resolve contestation."""
    UNRESOLVED = "UNRESOLVED"  # ← no resolution attempt or no decision
    RESOLVED = "RESOLVED"  # ← has resolution (but not necessarily "true")


@dataclass(frozen=True)
class ComputationalVerification:
    """L1: Did the computation execute as specified?
    
    This is the existing verification layer, now explicitly named.
    """
    status: str  # "PASS", "FAIL", "REFUTED", etc. (from VerificationStatus)


@dataclass(frozen=True)
class AssessedEvidenceState:
    """L2 evidence support with provenance.
    
    Critical invariant: SUPPORTED, NOT_SUPPORTED, or REFUTED states
    must have assessed_by set to a non-empty string.
    """
    state: EvidenceState
    assessed_by: str | None = None  # e.g. "verifier-v2", "cross_check", "domain_expert"
    assessment_method: str | None = None  # e.g. "independent_verifier", "contradiction_found"
    assessed_at: str | None = None  # ISO 8601 timestamp
    evidence_dependencies: list[str] = field(default_factory=list)  # what evidence was examined

    def __post_init__(self) -> None:
        """Validate that assessed states have provenance.

        The state is coerced to EvidenceState first, so a plain or misspelled string cannot skip the
        check (JG-1, F3). An unknown state raises ValueError.
        """
        state = EvidenceState(self.state)
        object.__setattr__(self, "state", state)
        if state in (EvidenceState.SUPPORTED, EvidenceState.NOT_SUPPORTED, EvidenceState.REFUTED):
            if not (isinstance(self.assessed_by, str) and self.assessed_by.strip()):
                raise ValueError(
                    f"EvidenceState.{state.value} requires assessed_by to be non-empty"
                )


@dataclass(frozen=True)
class AssessedDomainReview:
    """L3 domain review with provenance.
    
    Tracks who reviewed assumptions and rules, and whether expert attention is needed.
    """
    status: DomainReviewStatus
    reviewed_by: str | None = None  # e.g. "system", "domain_expert", "process_X"
    review_method: str | None = None  # e.g. "static_analysis", "expert_judgment"
    reviewed_at: str | None = None  # ISO 8601 timestamp
    assumptions_examined: list[str] = field(default_factory=list)  # which assumptions checked

    def __post_init__(self) -> None:
        """REVIEWED needs a reviewer (JG-1, F4). An unknown status raises ValueError."""
        status = DomainReviewStatus(self.status)
        object.__setattr__(self, "status", status)
        if status is DomainReviewStatus.REVIEWED:
            if not (isinstance(self.reviewed_by, str) and self.reviewed_by.strip()):
                raise ValueError("DomainReviewStatus.REVIEWED requires reviewed_by to be non-empty")


@dataclass(frozen=True)
class Challenge:
    """A recorded challenge to a claim.
    
    Preserves the actual disagreement: what was challenged, who raised it,
    what evidence contradicts it, and how the contradiction was found.
    """
    challenge_id: str  # unique identifier
    type: str  # e.g. "gps_spoofing", "evidence_contradiction", "assumption_violation"
    challenger_source: str  # who raised it: "cross_check", "verifier_v2", "external_report"
    challenged_claim: str  # what is being disputed (descriptive)
    counter_evidence: dict[str, Any]  # the contradicting evidence
    method: str | None = None  # how the contradiction was found (e.g. "distance_calculation")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "OPEN"  # OPEN, CLOSED, UNRESOLVED


@dataclass(frozen=True)
class ContestationResolution:
    """Outcome of attempt to resolve a contestation.
    
    Orthogonal from ContestationStatus: you can have CONTESTED + UNRESOLVED,
    meaning disagreement exists and hasn't been resolved.
    """
    status: ResolutionStatus
    method: str | None = None  # e.g. "independent_method", "domain_expert"
    authority: str | None = None  # who decided (future expansion)
    resolved_at: str | None = None  # when it was resolved


@dataclass(frozen=True)
class Contestation:
    """Records disagreement between evidence sources or interpretations.
    
    Critical invariant: CONTESTED status with resolution=None is valid.
    It means disagreement exists and this system has not resolved it.
    """
    status: ContestationStatus
    challenges: list[Challenge] = field(default_factory=list)
    resolution: ContestationResolution | None = None


@dataclass(frozen=True)
class VerifierIndependence:
    """Dimensions of verifier independence.
    
    Critical invariant: each dimension is independent.
    implementation=True does NOT imply method=True or data=True.
    """
    implementation: bool  # Different codebase
    method: bool  # Different algorithm or approach
    data: bool  # Different evidence source
    assumption: bool  # Different governing premise
    domain: bool  # Different expertise or validation


@dataclass(frozen=True)
class EpistemicAssessment:
    """Epistemic context for a decision, separate from authorization.
    
    This layer preserves information about:
    - Whether computation was verified (L1)
    - Whether evidence supports the claim (L2)
    - Whether assumptions and rules are appropriate (L3)
    - Whether evidence sources disagree (contestation)
    - What dimensions of the verifier are independent
    
    Critically: this layer does NOT replace Gate authorization.
    Gate remains ALLOW/DEFER/REFUSE based on L1 only (in Phase 1).
    """
    computational: ComputationalVerification
    evidence_support: AssessedEvidenceState
    domain_review: AssessedDomainReview
    contestation: Contestation
    independence: VerifierIndependence
