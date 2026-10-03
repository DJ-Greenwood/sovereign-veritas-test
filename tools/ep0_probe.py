"""EP-0 probe (registration: docs/EP0_PREREG.md): which insufficiency conditions does the real Gate tell apart?

  python tools/ep0_probe.py              exit 0 only on the RECORDED outcome
  python tools/ep0_probe.py --sabotage   every case is fed as C0; must exit 1
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402

RECORDED = ((True,) * 6, "0b91d8b0631d964206e3c647e2c62117d582a374ee9d470218bdc8af0781957d")  # pinned after the scored run

MISSING = object()
CASES = {  # id: (verification status or MISSING, sensor value or MISSING)
    "C0": ("PASS", True),
    "C1": ("REFUTED", True),
    "C2": ("FAIL", True),
    "C3": (MISSING, True),
    "C4": ("GARBLED", True),
    "C5": ("INSUFFICIENT_EVIDENCE", True),
    "C6": ("PASS", MISSING),
    "C7": ("PASS", "INACCESSIBLE"),
    "C8": ("PASS", "UNSEARCHED"),
}
REGISTERED = {
    "C0": ("ALLOW", ()),
    "C1": ("REFUSE", ("verification_refuted",)),
    "C2": ("REFUSE", ("verification_not_passed",)),
    "C3": ("REFUSE", ("verification_not_passed",)),
    "C4": ("REFUSE", ("verification_not_passed",)),
    "C5": ("DEFER", ("verification_insufficient_evidence",)),
    "C6": ("DEFER", ("missing_required_evidence:sensor",)),
    "C7": ("DEFER", ("missing_required_evidence:sensor",)),
    "C8": ("DEFER", ("missing_required_evidence:sensor",)),
}


def decide(case):
    status, sensor = CASES[case]
    verification = None if status is MISSING else {"status": status}
    meta = {} if sensor is MISSING else {"sensor": sensor}
    ev = EvidenceRecord(record_id=case, input_digest="abc", verification=verification,
                        action={"capability": "act", "requested": "go"}, metadata=meta)
    d = Gate().evaluate(ev, Capability("act", True, ("sensor",)),
                        RuntimeState(platform="ep0", python_version="3"))
    return d.decision, tuple(d.reasons)


def gate_reads_epistemic():
    """True if decision.py or workflow.py imports sovereign_veritas.epistemic."""
    for name in ("decision.py", "workflow.py"):
        tree = ast.parse(open(os.path.join(ROOT, "sovereign_veritas", name), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("epistemic"):
                return True
            if isinstance(node, ast.Import) and any(a.name.endswith("epistemic") for a in node.names):
                return True
    return False


def main(argv):
    sabotage = "--sabotage" in argv
    obs = {c: decide("C0" if sabotage else c) for c in CASES}
    for c, got in obs.items():
        mark = "AS REGISTERED" if got == REGISTERED[c] else "NOT AS REGISTERED"
        print(f"{c}  {got[0]:6} {','.join(got[1]) or '-':42} {mark}")
    pairs = set(obs.values())
    e1 = obs["C0"][0] == "ALLOW"
    e2 = sum(1 for v in obs.values() if v == obs["C1"]) == 1 and obs["C1"][0] != "ALLOW"
    e3 = obs["C2"] == obs["C3"] == obs["C4"] and obs["C2"][0] != "ALLOW"
    e4 = obs["C6"] == obs["C7"] == obs["C8"] and obs["C6"][0] != "ALLOW"
    e5 = len(pairs) == 5
    reads = gate_reads_epistemic()
    e6 = not reads
    held = (e1, e2, e3, e4, e5, e6)
    print(f"distinct (decision, reason) pairs: {len(pairs)} of 9 cases")
    print(f"decision.py/workflow.py import epistemic: {reads}")
    for k, h in enumerate(held, 1):
        print(f"{'HELD   ' if h else 'REFUTED'} E{k}")
    digest = hashlib.sha256(json.dumps({c: list(v) for c, v in obs.items()}, sort_keys=True).encode()).hexdigest()
    print(f"VERDICT {sum(held)} of 6 as registered")
    print(f"DIGEST {digest}")
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
