#!/usr/bin/env python3
"""recovery_admissibility.py - V15 (registered in docs/V15_RECOVERY_PREREG.md): when A (the autopilot's GNSS
position) is untrustworthy, can a recovery decision stay admissible if the second source B is unavailable,
stale, replayed or derived from A?

Software decisions on CONSTRUCTED inputs. No vehicle, no simulator, no physical claim.
  P0  the real Gate (EvidenceWorkflow) on the real vehicle_check, unchanged
  P1  P0 + rules on DECLARED fields (xpos_observed_at, xpos_root)      - written for V15
  P2  P0 + an authenticated B message (HMAC test key, Gate nonce, seq)  - written for V15

  python tools/recovery_admissibility.py              every case; exit 0 iff the outcome is the recorded one
  python tools/recovery_admissibility.py --sabotage   P2 skips its nonce check; the outcome must differ (exit 1)
Exit: 0 as recorded | 1 differs | 2 could not run.  Stdlib only.
"""
import argparse, hashlib, hmac, json, os, platform, subprocess, sys, tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("vehicle_action", os.path.join(ROOT, "tools", "vehicle_action.py"))
va = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("vehicle_action", va)
_spec.loader.exec_module(va)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal  # noqa: E402
from sovereign_veritas.package import sha256_hex  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

FENCE = {"lat_e7": 353632000, "lon_e7": -969270000, "radius_m": 300.0, "max_alt_m": 120.0}
T1 = 1000.0                     # decision time, s
TRUE_N = 100.0                  # the vehicle truly hovers 100 m north of the fence centre
A_COMP, A_HEALTHY = TRUE_N - 60.0, TRUE_N + 1.0
B_ERR = 2.0
FRESH_AGE, STALE_AGE, MAX_AGE = 0.5, 30.0, 2.0
KEY = b"v15-test-key-held-by-B-and-the-Gate-only"   # NOT a real key; the snapshot writer does not hold it
NONCE_NOW, NONCE_OLD = "n-t1-7f3a", "n-t0-19c2"     # the Gate's nonce for this decision / for the decision 30 s ago
SEQ_LAST_ACCEPTED, SEQ_OLD, SEQ_NOW = 90, 100, 131  # declared: the Gate last accepted seq 90 (B link degraded since)
ACTIONS = ("goto", "rtl", "land_hold", "land_nohold")
CASES = ("0", "1", "2", "3", "4", "5", "6", "7", "3f", "4f", "5f")
GOTO_N = 150.0


def pos(n):
    return va.offset(FENCE["lat_e7"], FENCE["lon_e7"], n, 0.0)


def b_message(value_n, observed_at, seq, nonce, root):
    """B's own message, MAC'd by B's device. 'root' is what B's device believes, not necessarily the truth."""
    body = {"n": value_n, "observed_at": observed_at, "seq": seq, "nonce": nonce, "root": root}
    mac = hmac.new(KEY, canonical_json(body).encode(), hashlib.sha256).hexdigest()
    return {"body": body, "mac": mac}


def build_case(c):
    """Returns (snapshot, b_msg). The snapshot carries P1's declared labels; b_msg is what P2 receives."""
    base = c.rstrip("f")
    a_n = A_HEALTHY if base in ("0", "6", "7") else A_COMP
    snap = dict(va.FakeVehicle.SCENARIOS["healthy_air"])
    snap["lat_e7"], snap["lon_e7"] = pos(a_n)
    if base in ("1", "6"):
        return snap, None
    if base in ("0", "2"):
        msg = b_message(TRUE_N + B_ERR, T1 - FRESH_AGE, SEQ_NOW, NONCE_NOW, "independent")
    elif base in ("3", "7"):   # stale: observed 30 s ago, when the vehicle was 40 m north (agrees with the spoof)
        msg = b_message(40.0 + B_ERR, T1 - STALE_AGE, SEQ_OLD, NONCE_OLD, "independent")
    elif base == "4":          # B's device honestly MACs a value it derived from A
        msg = b_message(a_n + B_ERR, T1 - FRESH_AGE, SEQ_NOW, NONCE_NOW, "gnss-derived")
    else:                      # 5: byte-for-byte replay of B's message from t1 - 30 s
        msg = b_message(40.0 + B_ERR, T1 - STALE_AGE, SEQ_OLD, NONCE_OLD, "independent")
    declared = {"observed_at": msg["body"]["observed_at"], "root": msg["body"]["root"]}
    if c in ("3f", "5f"):
        declared["observed_at"] = T1           # the forger rewrites the label, keeps the old MAC
        msg = {"body": dict(msg["body"], observed_at=T1), "mac": msg["mac"]}
    if c == "4f":
        declared["root"] = "independent"
    snap["xpos_lat_e7"], snap["xpos_lon_e7"] = pos(msg["body"]["n"])
    snap["xpos_source"] = "v15-constructed"
    snap["xpos_observed_at"], snap["xpos_root"] = declared["observed_at"], declared["root"]
    return snap, msg


def request(action):
    params = {}
    if action == "goto":
        params = {"alt_m": 20.0}
        params["lat_e7"], params["lon_e7"] = pos(GOTO_N)
    lim = {"min_fix_type": 3, "min_sats": 6, "min_battery_pct": 30, "max_nav_disagreement_m": 25.0}
    return {"schema": va.REQUEST_SCHEMA, "action": action, "params": params, "fence": dict(FENCE), "limits": lim}


class _Verdict:
    def __init__(self, verdict):
        self.verdict = verdict

    def verify(self, observation, prediction):
        return {"status": self.verdict}


class _NoEffect:
    def execute(self, action):
        return {"executed": None}


def gate(req, snap, verdict):
    """The real Gate through EvidenceWorkflow, with the verification verdict supplied; same capability, policy and
    declared-normal thermal status as tools/vehicle_action.py."""
    artifact = canonical_json(req).encode()
    predictor = va.RecordedSnapshot(snap, "v15-constructed-not-a-vehicle")
    verifier = _Verdict(verdict)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(va.VERIFIER_ID, verifier)
    registry.record_probe(va.VERIFIER_ID, passed=True)
    registry.record_probe(va.VERIFIER_ID, passed=True)
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"), metadata={}))
    wf = EvidenceWorkflow(sensor=va.Question(artifact), predictor=predictor, verifier=verifier, executor=_NoEffect(),
                          evidence_sink=LedgerSink(ledger), verifier_registry=registry)
    r = wf.run(record_id="v15", input_digest=sha256_hex(artifact),
               capability=Capability("vehicle_command", authorized=True, required_evidence=("verifier_probed",)),
               runtime=RuntimeState(platform="v15", python_version=platform.python_version(), thermal_status="normal",
                                    metadata={"thermal_status_source": "declared"}),
               action=ActionProposal("vehicle_command", req["action"], req["params"]),
               policy={"allow_only": ["takeoff", "goto", "land", "rtl"]},
               metadata={"verifier_probed": True}, verifier_id=va.VERIFIER_ID)
    return r.decision.decision


def nav_check(action, snap):
    """The real vehicle_check. land_hold navigates on A, so P1/P2 hold it to rtl's navigation rules; P0 can only
    send 'land', which has no rules."""
    return va.vehicle_check(request("rtl" if action == "land_hold" else action), snap)


def p0(action, snap, msg, sabotage):
    if action == "land_nohold":
        return "NOT EXPRESSIBLE", "P0's request schema has no descent without position hold"
    real = "land" if action == "land_hold" else action
    chk = va.vehicle_check(request(real), snap)
    return gate(request(real), snap, chk["verdict"]), chk["why"]


def p1(action, snap, msg, sabotage):
    if action == "land_nohold":
        return gate(request("land"), snap, "PASS"), "no position source used"
    chk = nav_check(action, snap)
    why = [chk["why"]] if chk["verdict"] == "FAIL" else []
    if "xpos_observed_at" in snap:
        if T1 - snap["xpos_observed_at"] > MAX_AGE:
            why.append(f"declared B age {T1 - snap['xpos_observed_at']:.1f} s > {MAX_AGE} s")
        if snap["xpos_root"] != "independent":
            why.append(f"declared B root {snap['xpos_root']}")
    return gate(request("land" if action == "land_hold" else action), snap, "FAIL" if why else "PASS"), \
        "; ".join(why) or "all rules hold"


def p2(action, snap, msg, sabotage):
    if action == "land_nohold":
        return gate(request("land"), snap, "PASS"), "no position source used"
    chk = nav_check(action, snap)
    why = [chk["why"]] if chk["verdict"] == "FAIL" else []
    if msg is not None:
        good_mac = hmac.compare_digest(msg["mac"], hmac.new(KEY, canonical_json(msg["body"]).encode(),
                                                            hashlib.sha256).hexdigest())
        if not good_mac:
            why.append("B message MAC invalid")
        if not sabotage and msg["body"]["nonce"] != NONCE_NOW:
            why.append("B message does not echo this decision's nonce")
        if msg["body"]["seq"] <= SEQ_LAST_ACCEPTED:
            why.append("B sequence number does not advance")
    return gate(request("land" if action == "land_hold" else action), snap, "FAIL" if why else "PASS"), \
        "; ".join(why) or "all rules hold"


POLICIES = {"P0": p0, "P1": p1, "P2": p2}


def justified(case, action):
    """The registered admissibility table: land_nohold ALLOW justified everywhere; navigating actions only in 0."""
    if action == "land_nohold":
        return "ALLOW"
    return "ALLOW" if case == "0" else "REFUSE"


def v15g():
    """Real tool, fake backend: a goto package, then a land package. Does the land package reference the goto?"""
    home = tempfile.mkdtemp(prefix="v15g-")
    env = dict(os.environ, HOME=home, USERPROFILE=home)
    tool = os.path.join(ROOT, "tools", "vehicle_action.py")
    common = ["--thermal-status", "normal", "--xpos-sigma", "3", "--max-disagreement", "25"]
    runs = []
    for link, action in (("fake:healthy_air", ["--action", "goto", "--north", "50", "--alt", "20"]),
                         ("fake:spoofed", ["--action", "land"])):
        out = subprocess.run([sys.executable, tool, "--link", link, *action, *common], env=env,
                             capture_output=True, text=True, check=False).stdout
        path = next((ln.split()[1] for ln in out.splitlines() if ln.startswith("package ")), None)
        if path is None:
            raise SystemExit(f"COULD NOT RUN: vehicle_action.py wrote no package:\n{out}")
        with open(path, encoding="utf-8") as fh:
            runs.append((json.load(fh), open(path, encoding="utf-8").read()))
    (goto_pkg, goto_txt), (land_pkg, land_txt) = runs
    goto_ids = {"artifact_sha256": goto_pkg["measurement"]["artifact_sha256"],
                "package_md5": hashlib.md5(goto_txt.encode()).hexdigest(),
                "output_sha256": goto_pkg["measurement"]["output_sha256"]}
    refs = {k: (v in land_txt) for k, v in goto_ids.items()}
    return {"goto_decision": goto_pkg["decision"]["decision"], "land_decision": land_pkg["decision"]["decision"],
            "references_found": sum(refs.values()), "checked": sorted(goto_ids)}


def run(sabotage):
    table = {}
    for pol, fn in POLICIES.items():
        for c in CASES:
            snap, msg = build_case(c)
            for a in ACTIONS:
                d, why = fn(a, snap, msg, sabotage)
                table[f"{pol}/{c}/{a}"] = {"decision": d, "why": why}
    return table, v15g()


def unjustified_allow(table, pol, cases, actions):
    return sorted(f"{c}/{a}" for c in cases for a in actions
                  if table[f"{pol}/{c}/{a}"]["decision"] == "ALLOW" and justified(c, a) != "ALLOW")


def predictions(t, g):
    d = lambda p, c, a: t[f"{p}/{c}/{a}"]["decision"]  # noqa: E731
    base = ("0", "1", "2", "3", "4", "5", "6", "7")
    rtl0 = {c: d("P0", c, "rtl") for c in CASES}
    v15a = ([c for c in base if rtl0[c] == "ALLOW"] == ["0", "3", "4", "5"]
            and "disagree" in t["P0/7/rtl"]["why"] and all(rtl0[c + "f"] == rtl0[c] for c in ("3", "4", "5")))
    v15b = all(d("P0", c, "land_hold") == "ALLOW" for c in base) and all(
        d("P0", c, "land_nohold") == "NOT EXPRESSIBLE" for c in CASES)
    v15c = d("P0", "2", "goto") == "REFUSE" and "disagree" in t["P0/2/goto"]["why"] and d("P0", "2", "land_hold") == "ALLOW"
    v15d = all(d("P0", "1", a) == d("P0", "6", a) for a in ACTIONS)
    p1_honest = [f"{c}/{a}" for c in base for a in ACTIONS if d("P1", c, a) != justified(c, a)]
    p1_forged = [c for c in ("3f", "4f", "5f") if d("P1", c, "rtl") == "ALLOW"]
    v15e = not p1_honest and p1_forged == ["3f", "4f", "5f"]
    p2_rtl = {c: d("P2", c, "rtl") for c in CASES}
    p2_bad = sorted(f"{c}/{a}" for c in CASES for a in ACTIONS if d("P2", c, a) != justified(c, a))
    v15f = (all(p2_rtl[c] == "REFUSE" for c in ("3", "3f", "5", "5f")) and p2_rtl["4"] == "ALLOW"
            and p2_rtl["4f"] == "ALLOW" and all(x.split("/")[0] in ("4", "4f") for x in p2_bad))
    v15g_ok = g["goto_decision"] == "ALLOW" and g["land_decision"] == "ALLOW" and g["references_found"] == 0
    healthy_refused = sum(d("P2", c, a) == "REFUSE" for c in ("6", "7") for a in ("rtl", "land_hold"))
    v15h = healthy_refused == 4 and all(d("P2", c, "land_nohold") == "ALLOW" for c in ("6", "7"))
    return [
        ("V15a P0 rtl: ALLOW 0,3,4,5; REFUSE 1,2,6,7; 7 for disagreement; forged = honest", v15a,
         f"rtl {rtl0}; unjustified {unjustified_allow(t, 'P0', base, ('rtl',))}"),
        ("V15b P0 land ALLOW in all 8; land_nohold not expressible", v15b,
         f"unjustified land_hold {unjustified_allow(t, 'P0', base, ('land_hold',))}"),
        ("V15c case 2: goto REFUSE (disagreement), land ALLOW on the same snapshot", v15c,
         f"goto {d('P0', '2', 'goto')} ({t['P0/2/goto']['why'][:50]}), land {d('P0', '2', 'land_hold')}"),
        ("V15d P0 cases 1 and 6 decide identically on every action", v15d,
         f"1 {[d('P0', '1', a) for a in ACTIONS]} 6 {[d('P0', '6', a) for a in ACTIONS]}"),
        ("V15e P1 honest = table (32/32); forged rtl ALLOW in 3f, 4f, 5f", v15e,
         f"honest mismatches {p1_honest}; forged ALLOW {p1_forged}"),
        ("V15f P2 rtl REFUSE 3,3f,5,5f; ALLOW 4,4f; only 4/4f off the table", v15f, f"off table {p2_bad}"),
        ("V15g land package references the goto it follows: 0", v15g_ok, json.dumps(g)),
        ("V15h P2 refuses healthy A in 6,7 (rtl, land_hold): 4 of 4; land_nohold ALLOW", v15h,
         f"refused {healthy_refused}"),
    ]


RECORDED = ((True, True, True, True, True, True, True, True),
            "5457298bd89ac2b16068e4713aa61109c53a1560335b5dcfbee45f92b3e2de9f")  # pinned after the registered run (docs/V15_RECOVERY_RESULTS.md)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sabotage", action="store_true", help="P2 skips its nonce check; the outcome must differ")
    ap.add_argument("--json", help="write the full decision table here")
    a = ap.parse_args()
    t, g = run(a.sabotage)
    print("V15 recovery admissibility | constructed inputs, no vehicle | registered in docs/V15_RECOVERY_PREREG.md")
    print(f"{'case':<5}" + "".join(f"{p + ' ' + x:<22}" for p in POLICIES for x in ("rtl", "land_hold")) + "table")
    for c in CASES:
        print(f"{c:<5}" + "".join(f"{t[f'{p}/{c}/{x}']['decision']:<22}" for p in POLICIES for x in ("rtl", "land_hold"))
              + justified(c, "rtl"))
    preds = predictions(t, g)
    held = [ok for _, ok, _ in preds]
    for name, ok, detail in preds:
        print(f"{'HELD' if ok else 'REFUTED':<8} {name:<84} {detail}")
    dg = sha256_hex(canonical_json({"table": t, "v15g": g, "held": held}).encode())
    print(f"VERDICT  {sum(held)} of {len(held)} as registered")
    print(f"DIGEST   {dg}")
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"table": t, "v15g": g, "held": held, "digest": dg}, fh, indent=1, sort_keys=True)
            fh.write("\n")
    if RECORDED is None:
        print("RECORDED none yet: first run")
        return 1
    same = (tuple(held), dg) == RECORDED
    print("OUTCOME  " + ("as recorded" if same else f"DIFFERS from the recorded {RECORDED}"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
