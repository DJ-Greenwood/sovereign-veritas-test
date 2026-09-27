#!/usr/bin/env python3
"""companion_action.py - may a consumer use a veritas-companion answer? The Gate decides from the
companion's own delegation log; a package lets anyone re-check. Registered in docs/COMPANION_ACTION.md.

veritas-companion (github.com/holland202/veritas-companion) logs one JSON line per question: which tier
answered (delegated_to), with what status (SUPPORTED, CACHED, UNCERTAIN, ESCALATE), and the answer
(final_result). This tool reads one line, runs the route check (tools/verify_package.companion_check),
and asks the Gate whether the answer may be used (capability use_answer). Only on ALLOW is the answer
released: written to a file in the sandbox folder, named by its hash. Tool answers are ALLOWed;
conflicts, escalations and large-model answers are DEFERred; unreadable records are REFUSEd.

  python tools/companion_action.py --log DELEGATIONS.jsonl [--line N | --all] [--out-dir DIR]
         [--thermal-status normal] [--sandbox ~/sv_sandbox]
Prints one line per package: line number, status, decision, package path.
Exit: 0 package(s) written, whatever the Gate decided | 2 could not run (unreadable log, bad line number)
"""
import argparse, hashlib, importlib.util, json, os, platform, sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.package import build_package, sha256_hex, write_package  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.thermal import read_zones  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

VERIFIER_ID = "companion-route-check-v0"
_spec = importlib.util.spec_from_file_location("vp_companion", os.path.join(ROOT, "tools", "verify_package.py"))
_vp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vp)
companion_check, COMPANION_SCHEMA, canon = _vp.companion_check, _vp.COMPANION_SCHEMA, _vp.canon


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Record:
    def __init__(self, artifact):
        self.artifact = artifact

    def observe(self):
        return self.artifact


class Logged:
    """The companion has already answered; its log line is the prediction."""
    def __init__(self, rec):
        self.rec = rec

    def predict(self, observation):
        return Prediction(value={"output_sha256": sha(canon(self.rec))}, model_id="veritas-companion")


class RouteCheck:
    def __init__(self, rec):
        self.rec = rec

    def verify(self, observation, prediction):
        if prediction.value.get("output_sha256") != sha(canon(self.rec)):
            return {"status": "FAIL"}
        return {"status": companion_check(self.rec)["verdict"]}


class Release:
    """Writes the answer to a path chosen here from its hash, never from the record."""
    def __init__(self, sandbox):
        self.dir = os.path.join(sandbox, "answers")

    def execute(self, action):
        data = action.parameters["value"].encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        os.makedirs(self.dir, exist_ok=True)
        path = os.path.join(self.dir, f"answer_{digest[:16]}.txt")
        with open(path, "wb") as fh:
            fh.write(data)
        return {"path": path, "sha256": digest}


def package_for(rec, where, thermal_status, sandbox):
    """One package for one delegation record (a dict). Returns the package."""
    artifact = canonical_json({"schema": COMPANION_SCHEMA, "record": rec}).encode("utf-8")
    chk = companion_check(rec)
    registry = VerifierRegistry(min_coverage=0.5)
    verifier = RouteCheck(rec)
    registry.register(VERIFIER_ID, verifier)
    for probe, want in (({"status": "SUPPORTED", "delegated_to": "deterministic", "final_result": "7"}, "PASS"),
                        ({"status": "UNCERTAIN", "delegated_to": "large_model", "final_result": "7"}, "INSUFFICIENT_EVIDENCE")):
        registry.record_probe(VERIFIER_ID, passed=companion_check(probe)["verdict"] == want)
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"),
                                 metadata={"device": platform.machine(), "python": platform.python_version()}))
    capability = Capability("use_answer", authorized=True, required_evidence=("verifier_probed",))
    runtime = RuntimeState(platform=platform.platform(), python_version=platform.python_version(),
                           thermal_status=thermal_status, metadata={"thermal_status_source": "declared"})
    policy = {"allow_only": ["use_answer"]}
    value = rec.get("final_result") if isinstance(rec, dict) else None
    action = ActionProposal("use_answer", "use_answer", {"value": value})
    wf = EvidenceWorkflow(sensor=Record(artifact), predictor=Logged(rec), verifier=verifier,
                          executor=Release(os.path.expanduser(sandbox)), evidence_sink=LedgerSink(ledger),
                          verifier_registry=registry)
    result = wf.run(record_id=f"companion-{where}", input_digest=sha256_hex(artifact), capability=capability,
                    runtime=runtime, action=action, policy=policy, metadata={"verifier_probed": True},
                    verifier_id=VERIFIER_ID)
    measurement = {"kind": "companion_route_check", "artifact_sha256": sha256_hex(artifact),
                   "output_sha256": sha(canon(rec)), "check": chk,
                   "released_sha256": result.execution_result["sha256"] if result.executed else None}
    zones = read_zones("/sys/class/thermal")
    return build_package(artifact=artifact, artifact_name=f"companion_record:{where}", measurement=measurement,
                         chain=ledger.all(), capability=capability, runtime=runtime, policy=policy,
                         verifier_id=VERIFIER_ID, validation=registry.validation(VERIFIER_ID), thermal=zones,
                         evidence_states={"thermal_status": "OPERATOR", "compute_budget": "DEFAULTED",
                                          "power_status": "DEFAULTED"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--line", type=int, default=None, help="1-based line of the log (default: the last)")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--out-dir", default=os.path.expanduser("~"))
    ap.add_argument("--thermal-status", default="normal")
    ap.add_argument("--sandbox", default=os.path.join(os.path.expanduser("~"), "sv_sandbox"))
    a = ap.parse_args()
    try:
        with open(os.path.expanduser(a.log), encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    except OSError as exc:
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)
    if not lines:
        print("COULD NOT RUN: the log is empty")
        sys.exit(2)
    picks = range(1, len(lines) + 1) if a.all else [a.line or len(lines)]
    os.makedirs(a.out_dir, exist_ok=True)
    for n in picks:
        if not 1 <= n <= len(lines):
            print(f"COULD NOT RUN: line {n} not in 1..{len(lines)}")
            sys.exit(2)
        try:
            rec = json.loads(lines[n - 1])
        except ValueError:
            rec = {"unparsed_line": lines[n - 1]}
        pkg = package_for(rec, f"{os.path.basename(a.log)}:{n}", a.thermal_status, a.sandbox)
        path = write_package(pkg, a.out_dir)
        st = rec.get("status") if isinstance(rec, dict) else None
        print(f"line {n:>4}  {str(st):<10} {pkg['decision']['decision']:<6} {pkg['decision']['reasons']}  {path}")


if __name__ == "__main__":
    main()
