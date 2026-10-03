"""G1 recount: one test per sv.gate/1 item against the real Gate (registration: docs/G1_RECOUNT_PREREG.md).

  python tools/g1_recount.py              exit 0 only on the RECORDED outcome
  python tools/g1_recount.py --selftest   anti-vacuity: stub rules must flip every NOT BUILT test (exit 0 if all flip)
  python tools/g1_recount.py --sabotage   the stub replaces the gate under test; must exit 1
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sovereign_veritas.capability import Capability, CapabilityRegistry  # noqa: E402
from sovereign_veritas.decision import Decision, Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402

RECORDED = ((True,) * 7, "9c9891f14e783deebaf1c00174c777153928b4fdb67412e2ecdb2e14d154bf8e")  # pinned after the scored run

REGISTERED = {"R1": "NOT BUILT", "R2": "NOT BUILT", "R3": "BUILT", "R4": "NOT BUILT",
              "R5": "NOT BUILT", "R6": "NOT BUILT", "R7": "NOT BUILT"}


class StubGate(Gate):
    """The rules sv.gate/1 would add, in their simplest form. Used only to show each test can say BUILT."""

    def __init__(self, budget=5):
        self.budget, self.count = budget, 0

    def evaluate(self, evidence, capability, runtime, policy=None, registry=None):
        d = super().evaluate(evidence, capability, runtime, policy=policy, registry=registry)
        if d.decision != "ALLOW":
            return d
        if (policy or {}).get("session_budget"):
            self.count += 1
            if self.count > policy["session_budget"]["count"]:
                return Decision("REFUSE", ("session_budget_exceeded",))
        if "DEFAULTED" in runtime.metadata.values():
            return Decision("REFUSE", ("runtime_defaulted",))
        if capability.max_steps is not None and "step_count" not in evidence.metadata:
            return Decision("REFUSE", ("step_count_missing",))
        states = evidence.metadata.get("evidence_states", {})
        for name in capability.required_evidence:
            if states.get(name) not in ("MEASURED", "DERIVED"):
                return Decision("REFUSE", (f"evidence_not_measured:{name}",))
        if capability.parent and registry is not None:
            seen, cur = {capability.name}, capability
            while cur.parent:
                if cur.parent in seen:
                    return Decision("REFUSE", ("grant_chain_cycle",))
                seen.add(cur.parent)
                cur = registry.get(cur.parent)
                if cur is None or cur.authorized is not True:
                    return Decision("REFUSE", ("grant_chain_gap",))
        return d


def rt(**meta):
    return RuntimeState(platform="g1", python_version="3", metadata=dict(meta))


def ev(cap="act", **meta):
    return EvidenceRecord(record_id="r", input_digest="abc", verification={"status": "PASS"},
                          action={"capability": cap, "requested": "go"}, metadata=dict(meta))


def r1(selftest):
    cls = RuntimeState
    if selftest:
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class NavRuntime(RuntimeState):
            nav_status: str = "OK"
        cls = NavRuntime
    try:
        cls(platform="g1", python_version="3", nav_status="LOST")
        return "BUILT", "nav_status accepted"
    except TypeError as exc:
        return "NOT BUILT", f"TypeError: {exc}"


def word_count(word, paths, planted):
    n = 0
    for p in paths:
        n += len(re.findall(word, open(p, encoding="utf-8").read(), flags=re.IGNORECASE))
    if planted:
        n += 1
    return n


def kernel_files():
    d = os.path.join(ROOT, "sovereign_veritas")
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".py")) + \
        [os.path.join(ROOT, "tools", "verify_package.py")]


def r2(selftest):
    n = word_count("latch", kernel_files(), selftest)
    return ("BUILT" if n else "NOT BUILT"), f"'latch' occurrences: {n}"


def r3(selftest):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "attack_harness.py"), "--round3"],
                       capture_output=True, text=True, cwd=ROOT)
    line = next((ln for ln in p.stdout.splitlines() if ln.startswith("A7/D3")), None)
    if line is None:
        return "ERROR", f"no A7/D3 line (exit {p.returncode}): {p.stderr.strip()[-200:]}"
    built = "first use ACCEPTED" in line and "replay refused" in line
    return ("BUILT" if built else "NOT BUILT"), " ".join(line.split())


def r4(gate):
    cap = Capability("act", True)
    ds = [gate.evaluate(ev(), cap, rt(), policy={"session_budget": {"count": 5}}).decision for _ in range(20)]
    return ("BUILT" if ds[5] == "REFUSE" and ds[:5] == ["ALLOW"] * 5 else "NOT BUILT"), \
        f"ALLOW {ds.count('ALLOW')} of 20; 6th = {ds[5]}"


def r5(selftest):
    n = word_count("allowed_authorizers", kernel_files(), selftest)
    return ("BUILT" if n else "NOT BUILT"), f"'allowed_authorizers' occurrences: {n}"


def r6(gate):
    a = gate.evaluate(ev(), Capability("act", True), rt(compute_budget="DEFAULTED")).decision
    b = gate.evaluate(ev(), Capability("act", True, max_steps=3), rt()).decision
    c = gate.evaluate(ev(fresh=True), Capability("act", True, ("fresh",)), rt()).decision
    built = all(x == "REFUSE" for x in (a, b, c))
    return ("BUILT" if built else "NOT BUILT"), f"a(DEFAULTED)={a} b(no step_count)={b} c(untagged evidence)={c}"


def r7(gate):
    reg = CapabilityRegistry()
    reg.register(Capability("c", False))
    reg.register(Capability("b", True, parent="c"))
    a_cap = reg.register(Capability("act", True, parent="b"))
    chain = gate.evaluate(ev(), a_cap, rt(), registry=reg).decision
    reg2 = CapabilityRegistry()
    reg2.register(Capability("b", True, parent="act"))
    a2 = reg2.register(Capability("act", True, parent="b"))
    cyc = gate.evaluate(ev(), a2, rt(), registry=reg2).decision
    built = chain == "REFUSE" and cyc == "REFUSE"
    return ("BUILT" if built else "NOT BUILT"), f"chain of 3 with unauthorized root={chain}; cycle={cyc}"


def collect(stub):
    gate_for = (lambda: StubGate()) if stub else (lambda: Gate())
    return {
        "R1": r1(stub), "R2": r2(stub), "R3": r3(stub), "R4": r4(gate_for()),
        "R5": r5(stub), "R6": r6(gate_for()), "R7": r7(gate_for()),
    }


def main(argv):
    selftest, sabotage = "--selftest" in argv, "--sabotage" in argv
    out = collect(stub=selftest or sabotage)
    for k, (verdict, detail) in out.items():
        print(f"{k}  {verdict:9}  registered {REGISTERED[k]:9}  {detail}")
    if selftest:
        flipped = [k for k in ("R1", "R2", "R4", "R5", "R6", "R7") if out[k][0] == "BUILT"]
        print(f"self-test: {len(flipped)} of 6 NOT BUILT tests flip to BUILT under the stub: {flipped}")
        return 0 if len(flipped) == 6 else 1
    held = tuple(out[k][0] == REGISTERED[k] for k in REGISTERED)
    built = sum(1 for k in out if out[k][0] == "BUILT")
    digest = hashlib.sha256(json.dumps({k: v[0] for k, v in out.items()}, sort_keys=True).encode()).hexdigest()
    print(f"BUILT {built} of 7")
    print(f"VERDICT {sum(held)} of 7 as registered")
    print(f"DIGEST {digest}")
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (held, digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
