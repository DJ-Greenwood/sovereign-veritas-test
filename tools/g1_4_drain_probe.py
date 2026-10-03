"""G1-4 drain probe (registration: docs/G1_4_DRAIN_PREREG.md). Every request goes through the real Gate first.

  python tools/g1_4_drain_probe.py              exit 0 only on the RECORDED outcome
  python tools/g1_4_drain_probe.py --sabotage   the budget checks are disabled; must exit 1
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

RECORDED = ((True,) * 6, "77c3c2c273ed30739f29cd44ccc60c064a47a3d69ac1b7e705404b9f1ef7fc53")  # pinned after the scored run
LIMIT = 5
ARMS = ("G0", "A", "B", "AB")
EXPECT = {"K0": (4, 4, 4, 4), "K1": (10, 5, 5, 5), "K2": (10, 5, 10, 5), "K3": (10, 10, 5, 5)}


def requests(cell):
    """(session, target, consumer) per request."""
    if cell == "K0":
        return [("s0", "t", "c0")] * 4
    if cell == "K1":
        return [("s0", "t", "c0")] * 10
    if cell == "K2":
        return [(f"s{i}", "t", "c0") for i in range(10)]
    if cell == "K3":
        return [("s0", "t", f"c{i % 2}") for i in range(10)]
    raise KeyError(cell)


def gate_allows(gate, i):
    ev = EvidenceRecord(record_id=f"r{i}", input_digest="abc", verification={"status": "PASS"},
                        action={"capability": "pay", "requested": "pay"}, metadata={})
    rt = RuntimeState(platform="g1-4", python_version="3")
    return gate.evaluate(ev, Capability("pay", True), rt).decision == "ALLOW"


def run(cell, arm, sabotage):
    gate = Gate()
    consumer_state = {}            # A: per consumer, counts by session and by target
    session_chain = {}             # B: the recorded chain per session (accepted actions so far)
    shared = {}                    # AB: a shared counter by target (assumed, see registration)
    accepted = 0
    for i, (sess, target, cons) in enumerate(requests(cell)):
        if not gate_allows(gate, i):
            continue
        ok = True
        if not sabotage:
            if arm in ("A", "AB"):
                st = consumer_state.setdefault(cons, {"sess": {}, "tgt": {}})
                if st["sess"].get(sess, 0) >= LIMIT or st["tgt"].get(target, 0) >= LIMIT:
                    ok = False
            if arm in ("B", "AB") and len(session_chain.get(sess, [])) >= LIMIT:
                ok = False
            if arm == "AB" and shared.get(target, 0) >= LIMIT:
                ok = False
        if ok:
            accepted += 1
            st = consumer_state.setdefault(cons, {"sess": {}, "tgt": {}})
            st["sess"][sess] = st["sess"].get(sess, 0) + 1
            st["tgt"][target] = st["tgt"].get(target, 0) + 1
            session_chain.setdefault(sess, []).append(f"r{i}")
            shared[target] = shared.get(target, 0) + 1
    return accepted


def collect(sabotage):
    return {cell: tuple(run(cell, arm, sabotage) for arm in ARMS) for cell in EXPECT}


def judge(obs, obs2):
    col = {arm: {cell: obs[cell][j] for cell in obs} for j, arm in enumerate(ARMS)}
    exp = {arm: {cell: EXPECT[cell][j] for cell in EXPECT} for j, arm in enumerate(ARMS)}
    d1 = all(v == 4 for v in obs["K0"])
    d2 = all(col["G0"][c] == 10 for c in ("K1", "K2", "K3"))
    d3 = col["A"]["K3"] == 10
    d4 = col["B"]["K2"] == 10
    holds_all = [arm for arm in ARMS if col[arm] == exp[arm] and all(
        col[arm][c] == (4 if c == "K0" else LIMIT) for c in EXPECT)]
    d5 = holds_all == ["AB"]
    d6 = obs == obs2
    return (d1, d2, d3, d4, d5, d6)


def main(argv):
    sabotage = "--sabotage" in argv
    obs, obs2 = collect(sabotage), collect(sabotage)
    print("cell  " + "  ".join(f"{a:>3}" for a in ARMS) + "   registered")
    for cell, row in obs.items():
        mark = "AS REGISTERED" if row == EXPECT[cell] else "NOT AS REGISTERED"
        print(f"{cell}    " + "  ".join(f"{v:>3}" for v in row) + f"   {EXPECT[cell]}  {mark}")
    held = judge(obs, obs2)
    for k, h in enumerate(held, 1):
        print(f"{'HELD   ' if h else 'REFUTED'} D{k}")
    digest = hashlib.sha256(json.dumps(obs, sort_keys=True).encode()).hexdigest()
    print(f"VERDICT {sum(held)} of 6 as registered")
    print(f"DIGEST {digest}")
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
