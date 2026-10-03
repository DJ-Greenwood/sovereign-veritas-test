#!/usr/bin/env python3
"""JG-1 probe: the five input-handling defects reported by James Greenwood (docs/JG1_PREREG.md).

Imports the real functions and checks the registered predictions P1-P5 against the fixed code.
  python tools/jg1_probe.py              exit 0 only if the outcome matches RECORDED
  python tools/jg1_probe.py --sabotage   swap in the pre-fix behaviour (P7): must exit 1

Prints one HELD/REFUTED line per prediction, a VERDICT line and a DIGEST.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sovereign_veritas.uncertainty as U  # noqa: E402
from sovereign_veritas.adversarial import ResourcePolicy  # noqa: E402
from sovereign_veritas.capability import Capability, CapabilityRegistry  # noqa: E402
from sovereign_veritas.epistemic import (  # noqa: E402
    AssessedDomainReview, AssessedEvidenceState, DomainReviewStatus, EvidenceState)
from sovereign_veritas.governance import CapabilityGovernor  # noqa: E402

RECORDED = None  # pinned after the first run, in a separate commit (WORKFLOW W4)


# ------------------------------------------------------------------ sabotage: pre-fix behaviour
def _old_branch_factor(self, thermal_status, compute_budget):
    if thermal_status in {"critical", "unsafe", "unavailable"}:
        return 0
    if compute_budget in {"exhausted", "unavailable"}:
        return 0
    if thermal_status in {"high", "warning"}:
        return self.constrained_branch_factor
    if compute_budget in {"constrained", "low"}:
        return self.constrained_branch_factor
    return self.normal_branch_factor


def _old_authorize(self, name, *, record_id, input_digest, reason, actor="external", metadata=None):
    from datetime import datetime, timezone
    from sovereign_veritas.evidence import EvidenceRecord
    ev = EvidenceRecord(record_id=record_id, input_digest=input_digest,
                        verification={"status": "PASS", "source": "capability_governor"},
                        capability=name, decision="ALLOW", reasons=(f"authorize:{name}", reason),
                        metadata=dict(metadata or {}), timestamp=datetime.now(timezone.utc).isoformat())
    self.sink.record(ev)
    return self.registry.authorize(name), ev


def _old_evidence_post_init(self):
    if self.state in (EvidenceState.SUPPORTED, EvidenceState.NOT_SUPPORTED, EvidenceState.REFUTED):
        if not self.assessed_by:
            raise ValueError(f"EvidenceState.{self.state.value} requires assessed_by to be non-empty")


def _old_review_post_init(self):
    return None


def _old_normalize(*, prediction_value=None, interval=None, method="unspecified",
                   coverage_target=None, nonconformity=None, extra=None):
    q = 0.5
    if interval is not None and len(interval) >= 2:
        try:
            lo, hi = float(interval[0]), float(interval[1])
            if lo <= hi and lo == lo and hi == hi:
                q += 0.2
        except (TypeError, ValueError):
            pass
    if coverage_target is not None:
        try:
            if 0.0 < float(coverage_target) <= 1.0:
                q += 0.2
        except (TypeError, ValueError):
            pass
    if nonconformity is not None:
        try:
            nc = float(nonconformity)
            if nc == nc:
                q += 0.1
        except (TypeError, ValueError):
            pass
    return {"method": method}, max(0.0, min(1.0, q))


def sabotage():
    ResourcePolicy.branch_factor = _old_branch_factor
    CapabilityGovernor.authorize = _old_authorize
    AssessedEvidenceState.__post_init__ = _old_evidence_post_init
    AssessedDomainReview.__post_init__ = _old_review_post_init
    U.normalize_uncertainty = _old_normalize


# ------------------------------------------------------------------ helpers
def outcome(fn):
    """Run fn; return its value, or the exception class name prefixed with 'raises '."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - the exception type is the observation
        return f"raises {type(e).__name__}"


class Sink:
    def __init__(self):
        self.records = []

    def record(self, r):
        self.records.append(r)


def q(**kw):
    return round(U.normalize_uncertainty(**kw)[1], 6)


# ------------------------------------------------------------------ predictions
def run():
    obs = {}
    p = ResourcePolicy()
    p1 = {
        "CRITICAL/available": outcome(lambda: p.branch_factor("CRITICAL", "available")),
        "bogus/available": outcome(lambda: p.branch_factor("bogus", "available")),
        "None/None": outcome(lambda: p.branch_factor(None, None)),
        "normal/EXHAUSTED": outcome(lambda: p.branch_factor("normal", "EXHAUSTED")),
        "5/available": outcome(lambda: p.branch_factor(5, "available")),
        "normal/normal": outcome(lambda: p.branch_factor("normal", "normal")),
        "warning/available": outcome(lambda: p.branch_factor("warning", "available")),
        "high/available": outcome(lambda: p.branch_factor("high", "available")),
        "hot/available": outcome(lambda: p.branch_factor("hot", "available")),
        "normal/available": outcome(lambda: p.branch_factor("normal", "available")),
        "cool/available": outcome(lambda: p.branch_factor("cool", "available")),
        "critical/available": outcome(lambda: p.branch_factor("critical", "available")),
    }
    want1 = {"CRITICAL/available": 0, "bogus/available": 0, "None/None": 0, "normal/EXHAUSTED": 0,
             "5/available": 0, "normal/normal": 0, "warning/available": 2, "high/available": 2,
             "hot/available": 2, "normal/available": 4, "cool/available": 4, "critical/available": 0}
    obs["P1"] = (p1, p1 == want1)

    sink, reg = Sink(), CapabilityRegistry()
    reg.register(Capability("write", False))
    gov = CapabilityGovernor(reg, sink)
    cap, rec = gov.authorize("never_registered", record_id="j2a", input_digest="d", reason="probe")
    cap2, rec2 = gov.authorize("write", record_id="j2b", input_digest="d", reason="probe")
    p2 = {"unregistered_returns": repr(cap), "unregistered_decision": rec.decision,
          "unregistered_status": rec.verification.get("status"), "records": len(sink.records),
          "registry_has_unregistered": reg.get("never_registered") is not None,
          "registered_decision": rec2.decision, "registered_authorized": bool(cap2 and cap2.authorized)}
    obs["P2"] = (p2, p2 == {"unregistered_returns": "None", "unregistered_decision": "REFUSE",
                            "unregistered_status": "FAIL", "records": 2,
                            "registry_has_unregistered": False, "registered_decision": "ALLOW",
                            "registered_authorized": True})

    def st(**kw):
        a = AssessedEvidenceState(**kw)
        return f"constructs {a.state!r}" if not isinstance(a.state, EvidenceState) else f"constructs {a.state.name}"
    p3 = {"supported": outcome(lambda: st(state="supported")),
          "SUPPORTED_no_assessor": outcome(lambda: st(state="SUPPORTED")),
          "SUPPORTED_with_assessor": outcome(lambda: st(state="SUPPORTED", assessed_by="x")),
          "UNVERIFIED_no_assessor": outcome(lambda: st(state=EvidenceState.UNVERIFIED))}
    obs["P3"] = (p3, p3 == {"supported": "raises ValueError", "SUPPORTED_no_assessor": "raises ValueError",
                            "SUPPORTED_with_assessor": "constructs SUPPORTED",
                            "UNVERIFIED_no_assessor": "constructs UNVERIFIED"})

    def dr(**kw):
        r = AssessedDomainReview(**kw)
        return f"constructs {r.status.name}" if isinstance(r.status, DomainReviewStatus) else f"constructs {r.status!r}"
    p4 = {"REVIEWED_no_reviewer": outcome(lambda: dr(status=DomainReviewStatus.REVIEWED)),
          "REVIEWED_str_with_reviewer": outcome(lambda: dr(status="REVIEWED", reviewed_by="x")),
          "NOT_REVIEWED_no_reviewer": outcome(lambda: dr(status=DomainReviewStatus.NOT_REVIEWED)),
          "unknown_status": outcome(lambda: dr(status="APPROVED", reviewed_by="x"))}
    obs["P4"] = (p4, p4 == {"REVIEWED_no_reviewer": "raises ValueError",
                            "REVIEWED_str_with_reviewer": "constructs REVIEWED",
                            "NOT_REVIEWED_no_reviewer": "constructs NOT_REVIEWED",
                            "unknown_status": "raises ValueError"})

    inf, nan = math.inf, math.nan
    p5 = {"ct_True": q(coverage_target=True), "ct_str": q(coverage_target="0.9"), "ct_0.9": q(coverage_target=0.9),
          "ct_1": q(coverage_target=1), "ct_1.5": q(coverage_target=1.5),
          "iv_inf": q(interval=(-inf, inf)), "iv_finite": q(interval=(1.0, 5.0)),
          "nc_inf": q(nonconformity=inf), "nc_nan": q(nonconformity=nan), "nc_True": q(nonconformity=True),
          "nc_0.12": q(nonconformity=0.12)}
    obs["P5"] = (p5, p5 == {"ct_True": 0.5, "ct_str": 0.5, "ct_0.9": 0.7, "ct_1": 0.7, "ct_1.5": 0.5,
                            "iv_inf": 0.5, "iv_finite": 0.7, "nc_inf": 0.5, "nc_nan": 0.5,
                            "nc_True": 0.5, "nc_0.12": 0.6})
    return obs


def main(argv):
    if "--sabotage" in argv:
        sabotage()
        print("SABOTAGE: the five functions are replaced by their pre-fix behaviour")
    obs = run()
    held = tuple(ok for _, ok in obs.values())
    for pid, (detail, ok) in obs.items():
        print(f"{'HELD   ' if ok else 'REFUTED'} {pid}  {json.dumps(detail, sort_keys=True)}")
    canon = json.dumps({k: v[0] for k, v in obs.items()}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canon.encode()).hexdigest()
    print(f"VERDICT {sum(held)} of {len(held)} as registered")
    print(f"DIGEST {digest}")
    if "--sabotage" in argv:
        return 1 if not all(held) else 0
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 0 if all(held) else 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
