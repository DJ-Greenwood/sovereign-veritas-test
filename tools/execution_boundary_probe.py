#!/usr/bin/env python3
"""XB-1 execution-boundary probe (docs/EXECUTION_BOUNDARY_PREREG.md).

Counts EXTERNAL EFFECTS with a counting executor and compares them with ledger records. Runs against
whatever `sovereign_veritas` package this checkout contains, so the same file measures 386716a, main,
and any candidate fix. Prints one line per case and a verdict against the registered predictions.

  python tools/execution_boundary_probe.py              predictions for the current code
  python tools/execution_boundary_probe.py --expect-fix predictions for the 'refuse before effect' fix
Exit: 0 every case as registered | 1 a case differs from its registration | 2 could not run
Stdlib only.
"""
import os, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.file_ledger import FileLedger  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402


class Sensor:
    def observe(self):
        return "observation"


class Predictor:
    def predict(self, observation):
        return Prediction(value="prediction", uncertainty=0.1, model_id="probe")


class Verifier:
    def verify(self, observation, prediction):
        return {"status": "PASS"}


class CountingExecutor:
    """The external world. `effects` is what happened out there, whatever the ledger says."""

    def __init__(self, delay=0.0, fail=False):
        self.effects, self.delay, self.fail = 0, delay, fail
        self._lock = threading.Lock()

    def execute(self, action):
        if self.fail:
            raise RuntimeError("executor failed before any effect")
        time.sleep(self.delay)
        with self._lock:
            self.effects += 1
        return {"effect": self.effects}


class BrokenSink:
    def record(self, record):
        raise OSError("simulated write failure (disk full)")


def records_in(sink):
    if isinstance(sink, BrokenSink):
        return 0
    ledger = sink.ledger
    return len(ledger.all()) if hasattr(ledger, "all") else len(ledger._records)


def run_once(wf, rid, granted=True):
    return wf.run(record_id=rid, input_digest="abc", capability=Capability("read_only", granted, ("fresh",)),
                  runtime=RuntimeState(platform="probe", python_version=sys.version.split()[0]),
                  action=ActionProposal(capability="read_only", requested="read", parameters={"t": 1}),
                  metadata={"fresh": True})


def make(sink, executor):
    return EvidenceWorkflow(sensor=Sensor(), predictor=Predictor(), verifier=Verifier(),
                            executor=executor, evidence_sink=sink)


def attempt(fn):
    try:
        fn()
        return None
    except Exception as exc:  # the probe records what escaped, it does not judge it
        return f"{type(exc).__name__}: {exc}"


def cases(tmp):
    out = {}

    ex, sink = CountingExecutor(), LedgerSink(Ledger())
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "a")), attempt(lambda: run_once(wf, "b"))]
    out["X0"] = (ex.effects, records_in(sink), [e for e in errs if e])

    ex, sink = CountingExecutor(), LedgerSink(Ledger())
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "r", granted=False))]
    out["X0r"] = (ex.effects, records_in(sink), [e for e in errs if e])

    ex, sink = CountingExecutor(), LedgerSink(Ledger())
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "dup")), attempt(lambda: run_once(wf, "dup"))]
    out["X1"] = (ex.effects, records_in(sink), [e for e in errs if e])

    path = os.path.join(tmp, "x2.jsonl")
    ex, sink = CountingExecutor(), LedgerSink(FileLedger(path))
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "dup")), attempt(lambda: run_once(wf, "dup"))]
    out["X2"] = (ex.effects, records_in(sink), [e for e in errs if e])

    path = os.path.join(tmp, "x3.jsonl")
    ex = CountingExecutor()
    errs = [attempt(lambda: run_once(make(LedgerSink(FileLedger(path)), ex), "dup"))]
    reloaded = LedgerSink(FileLedger(path))  # a new process would build its sink from disk
    errs.append(attempt(lambda: run_once(make(reloaded, ex), "dup")))
    out["X3"] = (ex.effects, records_in(LedgerSink(FileLedger(path))), [e for e in errs if e])

    ex, sink = CountingExecutor(delay=0.05), LedgerSink(Ledger())
    wf = make(sink, ex)
    errs = []
    threads = [threading.Thread(target=lambda: errs.append(attempt(lambda: run_once(wf, "race"))))
               for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    out["X4"] = (ex.effects, records_in(sink), [e for e in errs if e])

    ex, sink = CountingExecutor(), BrokenSink()
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "w"))]
    out["X5"] = (ex.effects, records_in(sink), [e for e in errs if e])

    ex, sink = CountingExecutor(fail=True), LedgerSink(Ledger())
    wf = make(sink, ex)
    errs = [attempt(lambda: run_once(wf, "f"))]
    status = sink.ledger.all()[0].metadata.get("execution_status") if sink.ledger.all() else None
    out["X6"] = (ex.effects, records_in(sink), [e for e in errs if e], status)
    return out


# (effects, records, number of escaped errors) as registered in docs/EXECUTION_BOUNDARY_PREREG.md
CURRENT = {"X0": (2, 2, 0), "X0r": (0, 1, 0), "X1": (2, 1, 1), "X2": (2, 1, 1), "X3": (2, 1, 1),
           "X4": (2, 1, 1), "X5": (1, 0, 1), "X6": (0, 1, 1)}
WITH_FIX = dict(CURRENT, X1=(1, 1, 1), X2=(1, 1, 1), X3=(1, 1, 1))


def main():
    expect = WITH_FIX if "--expect-fix" in sys.argv else CURRENT
    with tempfile.TemporaryDirectory() as tmp:
        got = cases(tmp)
    held = 0
    print(f"XB-1 | expecting {'the refuse-before-effect fix' if expect is WITH_FIX else 'the current code'}")
    for cid, exp in expect.items():
        g = got[cid]
        obs = (g[0], g[1], len(g[2]))
        ok = obs == exp
        if cid == "X6":
            ok = ok and g[3] == "FAILED"
        held += ok
        first = g[2][0][:70] if g[2] else "-"
        print(f"{'AS REGISTERED' if ok else 'NOT AS REGISTERED':<18} {cid:<4} effects {obs[0]} records {obs[1]}"
              f" errors {obs[2]}  (registered {exp[0]}/{exp[1]}/{exp[2]})  first error: {first}")
    print(f"VERDICT  {held} of {len(expect)} as registered")
    return 0 if held == len(expect) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ImportError as exc:
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)
