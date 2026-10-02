#!/usr/bin/env python3
"""XB-2 probe (docs/XB2_PREREG.md): can "this effect happens once, under current authority" become durable?

A1 is the REAL EvidenceWorkflow (with PR #8's has_record pre-check) over LedgerSink. A2-A4n are a reference
model written for this experiment, not kernel code. Every arm x case is scored by EXTERNAL EFFECTS (counted
at the external system) and the FINAL RECORD state, and compared with the registered table.

  python tools/xb2_boundary_probe.py
  python tools/xb2_boundary_probe.py --sabotage   A4's external system silently stops cooperating; P1 must
                                                  fail and the exit must be 1 (the probe can fail)
Exit: 0 every cell and P1-P5 as registered | 1 something differs | 2 could not run.  Stdlib only.
"""
import os, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402


class Crash(BaseException):
    """Process death. BaseException so nothing catches it as an ordinary error, as a kill would not be."""


class External:
    """The outside world. `cooperative`: de-duplicates by idempotency key and can be asked afterwards."""

    def __init__(self, cooperative=False, delay=0.0):
        self.cooperative, self.delay = cooperative, delay
        self.effects, self.done = 0, set()
        self._lock = threading.Lock()

    def apply(self, key, idempotent=False):
        time.sleep(self.delay)
        with self._lock:
            if idempotent and self.cooperative and key in self.done:
                return "already-applied"
            self.effects += 1
            self.done.add(key)
            return "applied"

    def lookup(self, key):
        if not self.cooperative:
            raise LookupError("external system cannot be asked")
        return key in self.done


# ------------------------------------------------------------------------------------- A1 (real)
class _Sensor:
    def observe(self):
        return "o"


class _Predictor:
    def predict(self, o):
        return Prediction(value="p", uncertainty=0.1, model_id="xb2")


class _Verifier:
    def verify(self, o, p):
        return {"status": "PASS"}


class _Exec:
    def __init__(self, ext, mode=None):
        self.ext, self.mode = ext, mode

    def execute(self, action):
        if self.mode == "crash_before":
            raise Crash()
        self.ext.apply(action.parameters["key"])
        if self.mode == "crash_after":
            raise Crash()
        if self.mode == "timeout":
            raise TimeoutError("response lost after the effect")
        return {"ok": True}


def _a1_run(sink, ext, key, mode=None):
    wf = EvidenceWorkflow(sensor=_Sensor(), predictor=_Predictor(), verifier=_Verifier(),
                          executor=_Exec(ext, mode), evidence_sink=sink)
    try:
        wf.run(record_id=key, input_digest="abc", capability=Capability("act", True, ("fresh",)),
               runtime=RuntimeState(platform="xb2", python_version=sys.version.split()[0]),
               action=ActionProposal(capability="act", requested="do", parameters={"key": key}),
               metadata={"fresh": True})
    except (Exception, Crash):
        pass


def _a1_state(sink, key):
    for r in sink.ledger.all():
        if r.record_id == key:
            return {"SUCCEEDED": "CONFIRMED", "FAILED": "FAILED"}.get(r.metadata.get("execution_status"), "OTHER")
    return "ABSENT"


def arm_a1(case):
    ext, sink = External(delay=0.05 if case == "C2" else 0.0), LedgerSink(Ledger())
    if case == "C3":
        return None  # decision and execution are one call: no deferred execution to revoke against
    if case in ("C0", "C1"):
        _a1_run(sink, ext, "k")
        if case == "C1":
            _a1_run(sink, ext, "k")
    elif case == "C2":
        ts = [threading.Thread(target=_a1_run, args=(sink, ext, "k")) for _ in range(2)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    elif case == "C4":
        _a1_run(sink, ext, "k", "crash_before")
        _a1_run(sink, ext, "k")  # restart: nothing durable says it was attempted, so the caller retries
    elif case == "C5":
        _a1_run(sink, ext, "k", "crash_after")
        _a1_run(sink, ext, "k")
    elif case == "C6":
        _a1_run(sink, ext, "k", "timeout")
        _a1_run(sink, ext, "k")  # caller retries after the ambiguous outcome
    return ext.effects, _a1_state(sink, "k")


# ------------------------------------------------------------------------- A2-A4n (reference model)
class Boundary:
    def __init__(self, arm, ext):
        self.arm, self.ext = arm, ext
        self.recheck = arm in ("A3", "A4", "A4n")
        self.idem = arm in ("A4", "A4n")
        self.ledger, self.lock = {}, threading.Lock()
        self.authorized = True

    def request(self, key, crash=None, timeout=False, revoke_after_decision=False):
        if not self.authorized:
            with self.lock:
                self.ledger.setdefault(key, "REFUSED")
            return
        if revoke_after_decision:  # the decision said ALLOW; authority is withdrawn before execution
            self.authorized = False
        with self.lock:  # atomic reservation: insert-if-absent
            if key in self.ledger:
                return
            self.ledger[key] = "INTENT"
        if self.recheck and not self.authorized:
            self.ledger[key] = "REFUSED"
            return
        if crash == "after_reserve":
            raise Crash()
        self.ext.apply(key, idempotent=self.idem)
        if crash == "after_effect":
            raise Crash()
        if timeout:
            self.ledger[key] = self._ask(key, fallback="UNKNOWN")
            return
        self.ledger[key] = "CONFIRMED"

    def _ask(self, key, fallback):
        if not self.idem:
            return fallback
        try:
            return "CONFIRMED" if self.ext.lookup(key) else None
        except LookupError:
            return fallback

    def recover(self):
        for key, st in list(self.ledger.items()):
            if st != "INTENT":
                continue
            if not self.idem:
                self.ledger[key] = "UNCONFIRMED"  # at-most-once: never retry an intent with no outcome
                continue
            answer = self._ask(key, fallback="UNCONFIRMED")
            if answer is None:  # the external system says it never happened: safe to apply once
                self.ext.apply(key, idempotent=True)
                answer = "CONFIRMED"
            self.ledger[key] = answer


def arm_model(arm, case):
    coop = arm == "A4" and "--sabotage" not in sys.argv
    ext = External(cooperative=coop, delay=0.05 if case == "C2" else 0.0)
    b = Boundary(arm, ext)
    try:
        if case == "C0":
            b.request("k")
        elif case == "C1":
            b.request("k")
            b.request("k")
        elif case == "C2":
            ts = [threading.Thread(target=b.request, args=("k",)) for _ in range(2)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        elif case == "C3":
            b.request("k", revoke_after_decision=True)
        elif case == "C4":
            b.request("k", crash="after_reserve")
        elif case == "C5":
            b.request("k", crash="after_effect")
        elif case == "C6":
            b.request("k", timeout=True)
            b.request("k")  # caller retries the same key
    except Crash:
        pass
    b.recover()  # restart
    return ext.effects, b.ledger.get("k", "ABSENT")


ARMS = ("A1", "A2", "A3", "A4", "A4n")
CASES = ("C0", "C1", "C2", "C3", "C4", "C5", "C6")
EXPECTED_EFFECTS = {c: (0 if c == "C3" else 1) for c in CASES}
C, U, K = "CONFIRMED", "UNCONFIRMED", "UNKNOWN"
REGISTERED = {
    "A1": {"C0": (1, C), "C1": (1, C), "C2": (2, C), "C3": None, "C4": (1, C), "C5": (2, C), "C6": (1, "FAILED")},
    "A2": {"C0": (1, C), "C1": (1, C), "C2": (1, C), "C3": (1, C), "C4": (0, U), "C5": (1, U), "C6": (1, K)},
    "A3": {"C0": (1, C), "C1": (1, C), "C2": (1, C), "C3": (0, "REFUSED"), "C4": (0, U), "C5": (1, U), "C6": (1, K)},
    "A4": {"C0": (1, C), "C1": (1, C), "C2": (1, C), "C3": (0, "REFUSED"), "C4": (1, C), "C5": (1, C), "C6": (1, C)},
    "A4n": {"C0": (1, C), "C1": (1, C), "C2": (1, C), "C3": (0, "REFUSED"), "C4": (0, U), "C5": (1, U), "C6": (1, K)},
}


def good(case, cell):
    """Expected effect count AND a definitive record that matches the world."""
    if cell is None:
        return None
    eff, st = cell
    want = EXPECTED_EFFECTS[case]
    return eff == want and ((st == C and eff == 1) or (st == "REFUSED" and eff == 0))


def main():
    got = {a: {c: (arm_a1(c) if a == "A1" else arm_model(a, c)) for c in CASES} for a in ARMS}
    cells_ok = 0
    print("XB-2 | effects, final record   (registered in docs/XB2_PREREG.md)")
    print("      " + "".join(f"{c:<22}" for c in CASES))
    for a in ARMS:
        row = []
        for c in CASES:
            g, r = got[a][c], REGISTERED[a][c]
            ok = g == r
            cells_ok += ok
            row.append(("N/A" if g is None else f"{g[0]}, {g[1]}") + ("" if ok else " (!)"))
        print(f"{a:<6}" + "".join(f"{x:<22}" for x in row))
    n_cells = len(ARMS) * len(CASES)
    print(f"cells as registered: {cells_ok} of {n_cells}")

    full = [a for a in ARMS if all(good(c, got[a][c]) for c in CASES)]
    a3_vs_a2 = [c for c in CASES if got["A3"][c] != got["A2"][c]]
    false_confirmed = [(a, c) for a in ARMS for c in CASES
                       if got[a][c] and got[a][c][1] == C and got[a][c][0] == 0]
    preds = [
        ("P1 only A4 reaches expected effects + true definitive record in all 7 cases", full == ["A4"], f"arms: {full}"),
        ("P2 A4n row equals A3 row (cooperation, not the gateway, gives the guarantee)",
         got["A4n"] == got["A3"], "equal" if got["A4n"] == got["A3"] else "differs"),
        ("P3 A3 differs from A2 only on C3", a3_vs_a2 == ["C3"], f"differs on {a3_vs_a2}"),
        ("P4 real workflow C6: effect happened, ledger says FAILED", got["A1"]["C6"] == (1, "FAILED"),
         f"A1 C6 = {got['A1']['C6']}"),
        ("P5 no arm records a false CONFIRMED", not false_confirmed, f"{false_confirmed or 'none'}"),
    ]
    held = 0
    for name, ok, detail in preds:
        held += ok
        print(f"{'AS REGISTERED' if ok else 'NOT AS REGISTERED':<18} {name:<82} {detail}")
    total_ok = cells_ok == n_cells and held == len(preds)
    print(f"VERDICT  {cells_ok}/{n_cells} cells, {held}/{len(preds)} predictions as registered")
    return 0 if total_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)
