#!/usr/bin/env python3
"""gate_impl.py - Standalone implementation of sv.gate/0 contract."""

import json
import math
import sys

STATUSES = {"PASS", "FAIL", "REFUTED", "INSUFFICIENT_EVIDENCE", "NOT_VERIFIED", "UNKNOWN"}
REFUSE_STATUS = {
    "FAIL": "verification_not_passed",
    "NOT_VERIFIED": "verification_not_passed",
    "UNKNOWN": "verification_not_passed",
    "REFUTED": "verification_refuted",
}
VOCAB = {
    "thermal_status": ({"normal", "cool"}, {"warning", "high", "hot", "critical", "unsafe"}),
    "compute_budget": ({"available", "constrained", "low"}, {"exhausted"}),
    "power_status": ({"stable"}, {"unsafe"}),
}


def coerce_status(value):
    if value is None:
        return "NOT_VERIFIED"
    s = str(value)
    return s if s in STATUSES else "UNKNOWN"


def runtime_available(rt):
    return all(
        isinstance(rt.get(f), str) and (rt[f] in ok or rt[f] in bad)
        for f, (ok, bad) in VOCAB.items()
    )


def runtime_healthy(rt):
    return all(
        isinstance(rt.get(f), str) and rt[f] in ok
        for f, (ok, _) in VOCAB.items()
    )


def as_quality(value):
    """Safely convert a JSON number to float; returns math.inf for overflow integers."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def quality_of(rec):
    """Read top-level evidence_quality if present, otherwise metadata quality."""
    if rec.get("evidence_quality") is not None:
        q = as_quality(rec["evidence_quality"])
        return 0.0 if q is None else q
    q = as_quality((rec.get("metadata") or {}).get("evidence_quality"))
    return 0.0 if q is None else q


def evaluate_gate(inp):
    rec = inp.get("record") or {}
    cap = inp.get("capability")
    registry = inp.get("capability_registry")
    runtime = inp.get("runtime") or {}
    policy = inp.get("policy") or {}
    reasons = []

    # Rule 1
    if not rec.get("input_digest"):
        return "REFUSE", ["evidence_invalid:missing_input_digest"]

    # Rule 2
    ver = rec.get("verification")
    status = coerce_status(None if ver is None else ver.get("status"))
    if status in REFUSE_STATUS:
        return "REFUSE", [REFUSE_STATUS[status]]
    if status == "INSUFFICIENT_EVIDENCE":
        reasons.append("verification_insufficient_evidence")
    elif status != "PASS":
        return "REFUSE", ["verification_not_passed"]

    # Rule 3
    if cap is None:
        return "REFUSE", ["capability_missing"]

    # Rule 4
    if cap.get("authorized") is not True:
        return "REFUSE", ["capability_not_authorized"]

    # Rule 5
    parent = cap.get("parent")
    if parent:
        if registry is None:
            return "REFUSE", ["capability_parent_requires_registry"]
        pcap = registry.get(parent) if isinstance(registry, dict) else None
        if pcap is None:
            return "REFUSE", [f"capability_parent_missing:{parent}"]
        if pcap.get("authorized") is not True:
            return "REFUSE", [f"capability_parent_not_authorized:{parent}"]

    # Rule 6
    action = rec.get("action") or {}
    if action.get("capability") and action.get("capability") != cap.get("name"):
        return "REFUSE", ["action_capability_mismatch"]

    # Rules 7 & 8
    if not runtime_available(runtime):
        return "REFUSE", ["runtime_state_unavailable"]
    if not runtime_healthy(runtime):
        reasons.append("runtime_not_healthy")

    # Rule 9
    meta = rec.get("metadata") or {}
    for name in cap.get("required_evidence") or []:
        if meta.get(name) is not True:
            reasons.append(f"missing_required_evidence:{name}")

    # Rule 10
    floor = cap.get("min_evidence_quality")
    if floor is not None:
        q = quality_of(rec)
        if not (math.isfinite(q) and 0.0 <= q <= 1.0):
            reasons.append(f"evidence_quality_invalid:{q!r}")
        elif q < floor:
            reasons.append(f"evidence_quality_below_threshold:{q:.4f}<{floor:.4f}")

    # Rule 11
    max_steps = cap.get("max_steps")
    if max_steps is not None:
        steps = meta.get("step_count")
        if steps is not None:
            if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
                reasons.append("invalid_step_count_metadata")
            elif steps > max_steps:
                return "REFUSE", [f"capability_max_steps_exceeded:{steps}>{max_steps}"]

    # Rule 12 & 13
    requested = action.get("requested")
    allow = policy.get("allow_only")
    if allow is not None and not isinstance(allow, list):
        return "REFUSE", ["policy_invalid:allow_only_must_be_a_collection"]
    if requested and allow is not None and requested not in allow:
        return "REFUSE", ["action_not_permitted_by_policy"]

    return ("DEFER", reasons) if reasons else ("ALLOW", [])


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        case = json.loads(line)
        dec, reas = evaluate_gate(case.get("input") or {})
        out = json.dumps({"id": case["id"], "decision": dec, "reasons": reas}, separators=(",", ":"))
        sys.stdout.write(out + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()