#!/usr/bin/env python3
"""FI end-to-end failure-injection harness (docs/FI_PREREG.md, registered at 6daa1fc).

Injects faults at the seams of the REAL EvidenceWorkflow / Gate / FileLedger / AnchoredFileLedger and into
the ledger files on disk. Counts EXTERNAL EFFECTS with a counting executor. Stdlib only. Deterministic.

  python tools/fault_injection.py              exit 0 only on the RECORDED outcome; 1 differs; 2 could not run
  python tools/fault_injection.py --sabotage   plants a bypass (sensor calls the executor before the gate):
                                               FI-4 must be REFUTED, exit 1
  python tools/fault_injection.py --json       also print the observations as JSON

The expected tuples below are copied from the registration. They are never edited after a run.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.dont_write_bytecode = True

try:
    import fcntl  # noqa: F401
    HAVE_FCNTL = True
except ImportError:
    HAVE_FCNTL = False

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.decision import Gate  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink  # noqa: E402
from sovereign_veritas.file_ledger import FileLedger  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

if HAVE_FCNTL:
    from sovereign_veritas.anchored_file_ledger import AnchoredFileLedger  # noqa: E402

# Pre-F3 pin (PR #23, commit df55508): FI-1, FI-2, FI-8 refuted. Kept as the record of the unfixed tree; this file is
# not re-run against that tree any more.
RECORDED_PRE_F3 = ((False, False, True, True, True, True, True, False, True),
                   "ac3b30e493d74b44f5d4b4b03d7622f0836186c080ddfada6addddef81123127")
# Post-F3 pin (this branch): FI-2 and FI-8 now hold as originally registered; FI-1 stays refuted (wrong U0 tuple).
RECORDED = ((False, True, True, True, True, True, True, True, True),
            "c77d529fa91ff00737e4ede58e189ec6695e2f9b143b1ea61f9e18e2c9062057")

# --------------------------------------------------------------------------- registered predictions
# (effects, records after reload, outcome, recorded decision / status note)
WORKFLOW_EXPECT = {
    "U0": (1, 1, "ok", "ALLOW"),
    "U0r": (0, 1, "ok", "REFUSE"),
    "U1": (0, 0, "raised RuntimeError", None),
    "U2": (0, 0, "raised RuntimeError", None),
    "U3": (0, 0, "raised RuntimeError", None),
    "U4": (0, 0, "raised TypeError", None),
    "U5": (0, 1, "ok", "REFUSE"),
    "U6": (0, 1, "ok", "REFUSE"),
    "U7": (0, 0, "raised ValueError", None),
    "U8": (0, 1, "ok", "REFUSE"),
    "U9": (0, 0, "raised ValueError", None),
    "U10": (0, 1, "ok", "DEFER"),
    "E1": (0, 1, "raised RuntimeError", "ALLOW/FAILED"),
    "E2": (1, 1, "raised RuntimeError", "ALLOW/FAILED"),
    "E3": (1, 0, "raised OSError", None),
    "E4": (1, 0, "raised Crash", None),
}
E4R_EXPECT = (2, 1)  # total effects, records
# stored-ledger faults: (plain FileLedger, AnchoredFileLedger); ("raises", key) or ("loads", n) or None = n/a
STORAGE_EXPECT = {
    "S1": (("raises", "invalid JSON at ledger index"), ("raises", "invalid JSON at ledger index")),
    "S2": (("raises", "tampered"), ("raises", "tampered")),
    "S6": (("raises", "chain broken"), ("raises", "chain broken")),
    "S3": (("loads", 2), ("raises", "truncated relative to anchor")),
    "S4": (("loads", 1), ("raises", "truncated relative to anchor")),
    "S5": (("loads", 3), ("raises", "mismatch against anchor")),
    "S7a": (None, ("loads", 3)),
    "S7c": (None, ("loads", 2)),
    "S7b": (None, ("loads", 0)),
    "S8": (None, ("loads", 4)),
}
KEYS = ("invalid JSON at ledger index", "tampered", "chain broken", "truncated relative to anchor",
        "mismatch against anchor", "anchor")
FI8_SET = {"U0r", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "U10"}


class Crash(BaseException):
    """A process death: not an Exception, so nothing in the workflow's `except Exception` can catch it."""


# --------------------------------------------------------------------------------------- fixtures
class Sensor:
    def observe(self):
        return "observation"


class Predictor:
    def __init__(self, uncertainty=0.1):
        self.uncertainty = uncertainty

    def predict(self, observation):
        return Prediction(value="prediction", uncertainty=self.uncertainty, model_id="fi")


class Verifier:
    def __init__(self, result=None):
        self.result = {"status": "PASS"} if result is None else result

    def verify(self, observation, prediction):
        return self.result


class RaisingSensor:
    def observe(self):
        raise RuntimeError("sensor fault")


class RaisingPredictor:
    def predict(self, observation):
        raise RuntimeError("predictor fault")


class RaisingVerifier:
    def verify(self, observation, prediction):
        raise RuntimeError("verifier fault")


class NoneVerifier:
    def verify(self, observation, prediction):
        return None


class CountingExecutor:
    """The external world. `effects` is what happened out there, whatever the ledger says."""

    def __init__(self, mode="ok"):
        self.effects, self.mode = 0, mode

    def execute(self, action):
        if self.mode == "fail_before":
            raise RuntimeError("executor failed before any effect")
        self.effects += 1
        if self.mode == "effect_then_raise":
            raise RuntimeError("executor timed out after the effect")
        return {"effect": self.effects}


class FailingSink:
    """Wraps a real sink; record() fails. has_record still answers from the real sink."""

    def __init__(self, inner, exc):
        self.inner, self.exc = inner, exc

    def has_record(self, record_id):
        return self.inner.has_record(record_id)

    def record(self, record):
        raise self.exc


class SpyGate(Gate):
    def __init__(self):
        self.decisions = []

    def evaluate(self, *args, **kwargs):
        d = super().evaluate(*args, **kwargs)
        self.decisions.append(d.decision)
        return d


class BypassSensor:
    """SABOTAGE: acts before the gate."""

    def __init__(self, inner, executor):
        self.inner, self.executor = inner, executor

    def observe(self):
        self.executor.execute(ActionProposal(capability="read_only", requested="read", parameters={}))
        return self.inner.observe()


class UngovernedWorkflow:
    """The simplest rival: sense, predict, act, record. No verifier, no gate, no registry, no runtime check."""

    def __init__(self, sensor, predictor, executor, sink):
        self.sensor, self.predictor, self.executor, self.sink = sensor, predictor, executor, sink

    def run(self, *, record_id, input_digest, capability, runtime, action, metadata, **_):
        obs = self.sensor.observe()
        pred = self.predictor.predict(obs)
        self.executor.execute(action)
        self.sink.record(EvidenceRecord(
            record_id=record_id, input_digest=input_digest,
            prediction={"value": pred.value, "uncertainty": pred.uncertainty, "model_id": pred.model_id},
            verification={}, capability=capability.name,
            action={"capability": action.capability, "requested": action.requested,
                    "parameters": dict(action.parameters)}, metadata=dict(metadata)))


def action():
    return ActionProposal(capability="read_only", requested="read", parameters={"t": 1})


def runtime(thermal="normal"):
    return RuntimeState(platform="fi", python_version=sys.version.split()[0], thermal_status=thermal)


def call_kwargs(rid, granted=True, digest="abc", thermal="normal"):
    return dict(record_id=rid, input_digest=digest,
                capability=Capability("read_only", granted, ("fresh",)), runtime=runtime(thermal),
                action=action(), metadata={"fresh": True})


def records_on_disk(path):
    """Fresh reload, as a new process would do."""
    try:
        return FileLedger(path)._records
    except Exception:
        return None


def last_status(recs):
    if not recs:
        return None
    rec = recs[-1]
    meta = rec.metadata
    return (rec.decision or "-") + ("/" + meta["execution_status"] if "execution_status" in meta else "")


def build(cell, path, executor, ungoverned=False, bypass=False):
    sensor, predictor, verifier = Sensor(), Predictor(), Verifier()
    registry, kw = None, {}
    sink = LedgerSink(FileLedger(path))
    if cell == "U1":
        sensor = RaisingSensor()
    elif cell == "U2":
        predictor = RaisingPredictor()
    elif cell == "U3":
        verifier = RaisingVerifier()
    elif cell == "U4":
        verifier = NoneVerifier()
    elif cell == "U5":
        verifier = Verifier({})
    elif cell == "U6":
        verifier = Verifier({"status": "pass"})
    elif cell == "U9":
        predictor = Predictor(float("nan"))
    elif cell == "U10":
        registry = VerifierRegistry(min_coverage=0.5)
    elif cell == "E3":
        sink = FailingSink(sink, OSError("simulated write failure (disk full)"))
    elif cell == "E4":
        sink = FailingSink(sink, Crash("process died after the effect"))
    if bypass:
        sensor = BypassSensor(sensor, executor)
    if ungoverned:
        return UngovernedWorkflow(sensor, predictor, executor, sink), None
    gate = SpyGate()
    return EvidenceWorkflow(sensor=sensor, predictor=predictor, verifier=verifier, executor=executor,
                            evidence_sink=sink, gate=gate, verifier_registry=registry), gate


def run_cell(cell, tmp, ungoverned=False, bypass=False):
    path = os.path.join(tmp, f"{cell}{'-u' if ungoverned else ''}.jsonl")
    ex = CountingExecutor({"E1": "fail_before", "E2": "effect_then_raise"}.get(cell, "ok"))
    wf, gate = build(cell, path, ex, ungoverned, bypass)
    kw = call_kwargs("r1", granted=(cell != "U0r"), digest=("" if cell == "U7" else "abc"),
                     thermal=("HOT!!" if cell == "U8" else "normal"))
    outcome = "ok"
    try:
        wf.run(**kw)
    except Crash:
        outcome = "raised Crash"
    except Exception as exc:
        outcome = f"raised {type(exc).__name__}"
    recs = records_on_disk(path)
    n = len(recs) if recs is not None else -1
    obs = {"effects": ex.effects, "records": n, "outcome": outcome, "recorded": last_status(recs),
           "allows": (gate.decisions.count("ALLOW") if gate else None)}
    return obs, path, ex


def run_e4r(tmp):
    path = os.path.join(tmp, "E4r.jsonl")
    ex = CountingExecutor()
    wf, _ = build("E4", path, ex)
    try:
        wf.run(**call_kwargs("r1"))
    except BaseException:
        pass
    wf2, _ = build("U0", path, ex)  # a restarted process: same ledger, working sink, same record id
    try:
        wf2.run(**call_kwargs("r1"))
    except Exception:
        pass
    recs = records_on_disk(path)
    return {"effects": ex.effects, "records": len(recs) if recs is not None else -1}


# ----------------------------------------------------------------------------------- storage cells
def make_base(tmp, name, anchored):
    path = os.path.join(tmp, f"{name}.jsonl")
    ledger = AnchoredFileLedger(path) if anchored else FileLedger(path)
    sink = LedgerSink(ledger)
    wf = EvidenceWorkflow(sensor=Sensor(), predictor=Predictor(), verifier=Verifier(),
                          executor=CountingExecutor(), evidence_sink=sink)
    for rid in ("a", "b", "c"):
        wf.run(**call_kwargs(rid))
    return path


def lines_of(path):
    return open(path, encoding="utf-8").read().splitlines(keepends=True)


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("".join(lines))


def apply_fault(fault, path, tmp):
    ls = lines_of(path)
    anchor = path + ".anchor"
    if fault == "S1":
        write_lines(path, ls[:-1] + [ls[-1][: len(ls[-1]) // 2]])
    elif fault == "S2":
        assert '"input_digest":"abc"' in ls[1]
        ls[1] = ls[1].replace('"input_digest":"abc"', '"input_digest":"abd"', 1)
        write_lines(path, ls)
    elif fault == "S6":
        write_lines(path, ls + [ls[-1]])
    elif fault == "S3":
        write_lines(path, ls[:-1])
    elif fault == "S4":
        write_lines(path, ls[:1])
    elif fault == "S5":
        alt = os.path.join(tmp, "alt-" + os.path.basename(path))
        write_lines(alt, ls[:2])
        FileLedger(alt).append(EvidenceRecord(record_id="evil", input_digest="zzz", verification={"status": "PASS"}))
        write_lines(path, lines_of(alt))
    elif fault == "S7a":
        os.remove(anchor)
    elif fault == "S7c":
        os.remove(anchor)
        write_lines(path, ls[:-1])
    elif fault == "S7b":
        os.remove(anchor)
        os.remove(path)
    elif fault == "S8":
        FileLedger(path).append(EvidenceRecord(record_id="d", input_digest="abc", verification={"status": "PASS"}))
    else:
        raise ValueError(fault)


def reload_obs(cls, path):
    try:
        led = cls(path)
        return ("loads", len(led._records))
    except Exception as exc:
        msg = str(exc)
        for key in KEYS:
            if key in msg:
                return ("raises", key)
        return ("raises", "other:" + msg[:40])


def storage_cells(tmp):
    out = {}
    for fault in STORAGE_EXPECT:
        plain_exp, anch_exp = STORAGE_EXPECT[fault]
        plain = anch = None
        if plain_exp is not None:
            p = make_base(tmp, f"{fault}-plain", anchored=False)
            apply_fault(fault, p, tmp)
            plain = reload_obs(FileLedger, p)
        if anch_exp is not None and HAVE_FCNTL:
            p = make_base(tmp, f"{fault}-anch", anchored=True)
            apply_fault(fault, p, tmp)
            anch = reload_obs(AnchoredFileLedger, p)
        out[fault] = {"plain": plain, "anchored": anch}
    return out


# ------------------------------------------------------------------------------------------ main
def collect(sabotage=False):
    tmp = tempfile.mkdtemp(prefix="fi-")
    try:
        wf, ung, paths = {}, {}, {}
        for cell in WORKFLOW_EXPECT:
            wf[cell], _, _ = run_cell(cell, tmp, bypass=sabotage)
        for cell in ["U0r"] + [f"U{i}" for i in range(1, 11)]:
            ung[cell], _, _ = run_cell(cell, tmp, ungoverned=True)
        return {"workflow": wf, "ungoverned": ung, "e4r": run_e4r(tmp), "storage": storage_cells(tmp)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def observed_tuple(o):
    rec = o["recorded"]
    return (o["effects"], o["records"], o["outcome"], rec)


def judge(obs):
    wf, st = obs["workflow"], obs["storage"]
    res = {}
    res["FI-1"] = all(observed_tuple(wf[c]) == WORKFLOW_EXPECT[c] for c in ("U0", "U0r"))
    ups = [f"U{i}" for i in range(1, 11)]
    res["FI-2"] = all(observed_tuple(wf[c]) == WORKFLOW_EXPECT[c] for c in ups) and all(wf[c]["effects"] == 0 for c in ups)
    res["FI-3"] = (all(observed_tuple(wf[c]) == WORKFLOW_EXPECT[c] for c in ("E1", "E2", "E3", "E4"))
                   and (obs["e4r"]["effects"], obs["e4r"]["records"]) == E4R_EXPECT)
    ia = sorted(c for c, o in wf.items() if o["allows"] is not None and o["effects"] > o["allows"])
    ib = sorted(c for c, o in wf.items() if o["effects"] > max(o["records"], 0))
    ic = sorted(c for c, o in wf.items()
                if o["recorded"] and "/" in o["recorded"]
                and ((o["recorded"].endswith("SUCCEEDED")) != (o["effects"] >= 1)))
    obs["invariants"] = {"I-A": ia, "I-B": ib, "I-C": ic}
    res["FI-4"] = ia == [] and ib == ["E3", "E4"] and ic == ["E2"]

    def match(fault, side):
        exp = STORAGE_EXPECT[fault][0 if side == "plain" else 1]
        return st[fault][side] == (tuple(exp) if exp else None)

    res["FI-5"] = all(match(f, s) for f in ("S1", "S2", "S6") for s in ("plain", "anchored")) if HAVE_FCNTL else None
    res["FI-6"] = all(match(f, s) for f in ("S3", "S4", "S5") for s in ("plain", "anchored")) if HAVE_FCNTL else None
    res["FI-7"] = all(match(f, "anchored") for f in ("S7a", "S7c", "S7b", "S8")) if HAVE_FCNTL else None
    gov0 = {c for c, o in wf.items() if c in obs["ungoverned"] and o["effects"] == 0}
    fi8 = {c for c in gov0 if obs["ungoverned"][c]["effects"] > 0}
    obs["fi8"] = {"set": sorted(fi8), "governed_zero_cells": len(gov0 | {c for c in obs["ungoverned"] if wf[c]["effects"] == 0}),
                  "ungoverned_cells_with_effect": len(fi8)}
    res["FI-8"] = fi8 == FI8_SET
    return res


def digest_of(obs):
    return hashlib.sha256(json.dumps(obs, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def main(argv):
    sab = "--sabotage" in argv
    if not HAVE_FCNTL:
        print("COULD NOT RUN anchored cells: fcntl is unavailable on this platform (FI-5/6/7 need AnchoredFileLedger)")
    if sab:
        print("SABOTAGE: the sensor calls the executor before the gate")
    obs = collect(sabotage=sab)
    res = judge(obs)
    again = collect(sabotage=sab)
    judge(again)
    res["FI-9"] = digest_of(obs) == digest_of(again)

    for c, exp in WORKFLOW_EXPECT.items():
        got = observed_tuple(obs["workflow"][c])
        print(f"{'AS REGISTERED    ' if got == exp else 'NOT AS REGISTERED'} {c:<4} got {got}  registered {exp}")
    e = obs["e4r"]
    print(f"{'AS REGISTERED    ' if (e['effects'], e['records']) == E4R_EXPECT else 'NOT AS REGISTERED'} E4r  got {(e['effects'], e['records'])}  registered {E4R_EXPECT}")
    for f, exp in STORAGE_EXPECT.items():
        for side, ex in zip(("plain", "anchored"), exp):
            got = obs["storage"][f][side]
            if ex is None and got is None:
                continue
            ok = got == (tuple(ex) if ex else None)
            print(f"{'AS REGISTERED    ' if ok else 'NOT AS REGISTERED'} {f:<4} {side:<8} got {got}  registered {ex}")
    print("invariant violations:", json.dumps(obs["invariants"]))
    print("rival (ungoverned) effects where governed has none:", json.dumps(obs["fi8"]))
    held = []
    for k in sorted(res, key=lambda s: int(s.split("-")[1])):
        v = res[k]
        label = "NOT RUN " if v is None else ("HELD   " if v else "REFUTED")
        print(f"{label} {k}")
        held.append(v)
    ran = [h for h in held if h is not None]
    digest = digest_of(obs)
    print(f"VERDICT {sum(ran)} of {len(held)} as registered" + ("" if None not in held else f" ({held.count(None)} not run)"))
    print(f"DIGEST {digest}")
    if "--json" in argv:
        print(json.dumps(obs, sort_keys=True, default=str, indent=1))
    if not HAVE_FCNTL:
        return 2
    if sab:
        return 0 if all(ran) else 1
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 0 if all(ran) else 1
    return 0 if (tuple(held), digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
