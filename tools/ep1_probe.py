"""EP-1 probe (registration: docs/EP1_PREREG.md). Real Gate for every decision; world model and policies as registered.

  python tools/ep1_probe.py              exit 0 only on the RECORDED outcome
  python tools/ep1_probe.py --sabotage   P_gen is given the condition labels; must exit 1
"""
from __future__ import annotations

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

RECORDED = ((True,) * 7, "a866bbdc092edb138eb4fbcc737a7c5174506e1b7868d52c1d9786183b51a316")  # pinned after the scored run
MISSING = object()


def gate(status="PASS", sensor=True, thermal="normal"):
    meta = {} if sensor is MISSING else {"sensor": sensor}
    ev = EvidenceRecord(record_id="r", input_digest="abc", verification={"status": status},
                        action={"capability": "act", "requested": "go"}, metadata=meta)
    rt = RuntimeState(platform="ep1", python_version="3", thermal_status=thermal)
    d = Gate().evaluate(ev, Capability("act", True, ("sensor",)), rt)
    return d.decision, tuple(d.reasons)


# Initial state of each condition, and how the world responds to retry / search (registered model).
INITIAL = {"M": ("PASS", MISSING), "I": ("PASS", "INACCESSIBLE"), "U": ("PASS", "UNSEARCHED"),
           "O": ("PASS", "OUT_OF_SCOPE"), "S": ("INSUFFICIENT_EVIDENCE", True)}


def after(cond, state, op):
    status, sensor = state
    if cond in ("I", "S") and op == "retry":
        return ("PASS", True)
    if cond == "U" and op == "search":
        return ("PASS", True)
    return state


def policy_ops(cond, knows, budget):
    """Operations the caller performs after the first DEFER, before giving up."""
    if budget == 0:
        return []
    if not knows:
        return ["retry"] * budget
    return {"I": ["retry"], "S": ["retry"], "U": ["search", "retry"], "M": [], "O": []}[cond][:budget + 1]


def play(cond, knows, budget):
    state = INITIAL[cond]
    d = gate(*state)
    spent = 0
    for op in policy_ops(cond, knows, budget):
        if d[0] != "DEFER":
            break
        state = after(cond, state, op)
        spent += op == "retry"
        if op == "retry":
            d = gate(*state)
    return d[0], spent


def main(argv):
    sabotage = "--sabotage" in argv
    first = {c: gate(*INITIAL[c]) for c in INITIAL}
    rm, rd = gate(thermal=None), gate()
    print("first decision per condition:")
    for c, v in first.items():
        print(f"  {c}  {v[0]:6} {','.join(v[1])}")
    print(f"  RM {rm[0]:6} {','.join(rm[1])}")
    print(f"  RD {rd[0]:6} {','.join(rd[1]) or '-'}")
    runs = {}
    for budget in (3, 0):
        for c in INITIAL:
            runs[(c, budget)] = {"P_gen": play(c, sabotage, budget), "P_dist": play(c, True, budget)}
    print("outcome (final decision, retries spent):")
    for (c, b), v in runs.items():
        print(f"  R={b} {c}  P_gen {v['P_gen']}  P_dist {v['P_dist']}")

    f1 = first["M"] == first["I"] == first["U"] == first["O"] == ("DEFER", ("missing_required_evidence:sensor",))
    f2 = rm == ("REFUSE", ("runtime_state_unavailable",)) and first["M"][0] == "DEFER" and rd[0] == "ALLOW"
    r = lambda c, b=3: runs[(c, b)]  # noqa: E731
    f3 = r("I")["P_gen"] == r("I")["P_dist"] == ("ALLOW", 1)
    f4 = r("U")["P_gen"] == ("DEFER", 3) and r("U")["P_dist"][0] == "ALLOW"
    f5 = (r("O")["P_gen"] == ("DEFER", 3) and r("O")["P_dist"] == ("DEFER", 0)
          and r("M")["P_gen"] == r("O")["P_gen"] and r("M")["P_dist"] == r("O")["P_dist"])
    f6 = all(runs[(c, 0)]["P_gen"] == runs[(c, 0)]["P_dist"] for c in INITIAL)
    f7 = r("I")["P_gen"] == r("I")["P_dist"] == r("S")["P_gen"] == r("S")["P_dist"]
    held = (f1, f2, f3, f4, f5, f6, f7)
    for i, h in enumerate(held, 1):
        print(f"{'HELD   ' if h else 'REFUTED'} F{i}")
    blob = {"first": {c: list(v) for c, v in first.items()}, "rm": list(rm), "rd": list(rd),
            "runs": {f"{c}|{b}": {k: list(x) for k, x in v.items()} for (c, b), v in runs.items()}}
    digest = hashlib.sha256(json.dumps(blob, sort_keys=True).encode()).hexdigest()
    print(f"VERDICT {sum(held)} of 7 as registered")
    print(f"DIGEST {digest}")
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
