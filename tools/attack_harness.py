#!/usr/bin/env python3
"""attack_harness.py - false approvals per attack class against tools/verify_package.py.

Registered in docs/ATTACK_HARNESS.md (P0-P7) before it was built. The attacker has the committed
vehicle packages but neither the author's signing key nor write access to the witness log. Every
forgery is resealed with the verifier's OWN functions (vehicle_check, replay_gate, sha, canon), which
is the attacker's best move. Keys are throwaway, made in a temporary directory; the phone's
~/.ssh/sv_package_ed25519 is never touched.

  python tools/attack_harness.py [--runs DIR ...] [--json OUT]
Exit: 0 every registered prediction held | 1 one failed | 2 could not run
"""
import argparse, base64, copy, glob, importlib.util, json, os, shutil, subprocess, sys, tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RUNS = ["runs/vehicle_sitl", "runs/vehicle_sitl_v11/*", "runs/vehicle_sitl_v12", "runs/vehicle_sitl_v13"]
EAST_100M_E7 = 11018  # 100 m of longitude at 35.36 N, in degrees * 1e7


def load_verifier():
    spec = importlib.util.spec_from_file_location("vp_attack", os.path.join(ROOT, "tools", "verify_package.py"))
    vp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vp)
    return vp


class Keys:
    """A throwaway author key and attacker key, and an allowed_signers file naming only the author."""

    def __init__(self, vp, tmp):
        self.vp, self.tmp, self.exe = vp, tmp, shutil.which("ssh-keygen")
        if self.exe is None:
            raise OSError("ssh-keygen not found")
        for who in ("author", "attacker"):
            subprocess.run([self.exe, "-q", "-t", "ed25519", "-N", "", "-C", who, "-f", os.path.join(tmp, who)],
                           check=True, capture_output=True)
        with open(os.path.join(tmp, "author.pub")) as fh:
            pub = fh.read().split()
        self.allowed = os.path.join(tmp, "allowed_signers")
        with open(self.allowed, "w") as fh:
            fh.write(f"author {pub[0]} {pub[1]}\n")
        self.n = 0

    def sign(self, who, data):
        self.n += 1
        path = os.path.join(self.tmp, f"blob{self.n}")
        with open(path, "wb") as fh:
            fh.write(data)
        subprocess.run([self.exe, "-Y", "sign", "-q", "-f", os.path.join(self.tmp, who), "-n", self.vp.NAMESPACE, path],
                       check=True, capture_output=True)
        return path + ".sig"

    def valid(self, data, sig):
        return self.vp.check_signature(data, sig, self.allowed, "author")[0]


def reseal(vp, pkg):
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def request_of(pkg):
    return json.loads(base64.b64decode(pkg["artifact"]["bytes_b64"]))


def recompute_all(vp, pkg, req=None):
    """Re-derive everything downstream of the request and the observation, as the verifier would."""
    rec, m = pkg["provenance"]["chain"][-1]["record"], pkg["measurement"]
    if req is not None:
        raw = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
        pkg["artifact"]["bytes_b64"] = base64.b64encode(raw).decode()
        pkg["artifact"]["sha256"] = m["artifact_sha256"] = rec["input_digest"] = vp.sha(raw)
        rec["action"]["parameters"] = req.get("params") or {}
    req = request_of(pkg)
    snap = m["telemetry_before"]
    m["output_sha256"] = vp.sha(vp.canon(snap))
    m["check"] = vp.vehicle_check(req, snap)
    rec["verification"] = {"status": m["check"]["verdict"]}
    rec["prediction"]["value"]["output_sha256"] = m["output_sha256"]
    gi = pkg["gate_inputs"]
    d, r = vp.replay_gate(rec, gi["capability"], gi["capability_registry"], pkg["resource_state"]["runtime"], gi["policy"])
    rec["decision"], rec["reasons"] = d, list(r)
    pkg["decision"] = {"decision": d, "reasons": list(r)}
    return reseal(vp, pkg)


def flip(pkg):
    d = pkg["decision"]
    if d["decision"] == "ALLOW":
        pkg["decision"] = {"decision": "REFUSE", "reasons": ["verification_not_passed"]}
    else:
        pkg["decision"] = {"decision": "ALLOW", "reasons": []}
    return pkg


def healthy(snap):
    s = dict(snap, gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=100)
    s["xpos_lat_e7"], s["xpos_lon_e7"] = s["lat_e7"], s["lon_e7"]
    return s


def dump(pkg):
    return (json.dumps(pkg, indent=2, sort_keys=True) + "\n").encode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="*", default=DEFAULT_RUNS)
    ap.add_argument("--json")
    a = ap.parse_args()
    try:
        vp = load_verifier()
        files = sorted({f for pat in a.runs for f in glob.glob(os.path.join(ROOT, pat, "sv_package_*.json"))})
        corpus = []
        for f in files:
            with open(f, "rb") as fh:
                data = fh.read()
            pkg = json.loads(data)
            corpus.append((pkg["provenance"]["chain"][-1]["record"]["timestamp"], os.path.relpath(f, ROOT), data, pkg))
        corpus.sort()
        if not corpus:
            raise OSError("no packages found")
        tmp = tempfile.mkdtemp(prefix="sv_attack_")
        keys = Keys(vp, tmp)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)

    # The author signs and witnesses every genuine package, oldest first.
    witness = os.path.join(tmp, "packages.log")
    with open(witness, "w") as fh:
        fh.write(vp.WITNESS_HEADER + "\n")
        for i, (_, _, _, pkg) in enumerate(corpus, 1):
            fh.write(f"{i} {pkg['package_sha256']}\n")
    genuine_sig = {name: keys.sign("author", data) for _, name, data, _ in corpus}

    def judge(data, sigs):
        """(D0, D1, D2) acceptance of these bytes, given the signatures the attacker can attach."""
        pkg = json.loads(data)
        d0 = all(ok for _, ok, _ in vp.verify(pkg))
        d1 = d0 and any(keys.valid(data, s) for s in sigs)
        d2 = d1 and vp.check_witness(pkg, witness)[0]
        return d0, d1, d2

    def forged(src_name, pkg):
        data = dump(pkg)
        return judge(data, [genuine_sig[src_name], keys.sign("attacker", data)])

    results = {}

    def record(cls, name, verdicts, failed_checks=None):
        results.setdefault(cls, []).append({"package": name, "D0": verdicts[0], "D1": verdicts[1], "D2": verdicts[2],
                                            "failed": failed_checks or []})

    def failed_names(pkg):
        return [n for n, ok, _ in vp.verify(pkg) if not ok]

    latest = corpus[-1][1]
    for _, name, data, pkg in corpus:
        record("GENUINE", name, judge(data, [genuine_sig[name]]))
        p1 = flip(copy.deepcopy(pkg))
        record("A1", name, forged(name, p1), failed_names(p1))
        p2 = copy.deepcopy(pkg)
        rec = p2["provenance"]["chain"][-1]["record"]
        flip(p2)
        rec["decision"], rec["reasons"] = p2["decision"]["decision"], list(p2["decision"]["reasons"])
        reseal(vp, p2)
        record("A2", name, forged(name, p2), failed_names(p2))
        if name != latest:
            record("A6", name, judge(data, [genuine_sig[name]]))
    record("A7", latest, judge(corpus[-1][2], [genuine_sig[latest]]))

    passes = [pkg["measurement"]["telemetry_before"] for _, _, _, pkg in corpus if pkg["measurement"]["check"]["verdict"] == "PASS"]
    for _, name, _, pkg in corpus:
        if pkg["decision"]["reasons"] == ["verification_not_passed"]:
            p3 = copy.deepcopy(pkg)
            p3["measurement"]["telemetry_before"] = healthy(p3["measurement"]["telemetry_before"])
            recompute_all(vp, p3)
            record("A3", name, forged(name, p3), failed_names(p3))
            best = None
            for snap in passes:  # the attacker tries every real PASS observation and keeps the best
                p4 = copy.deepcopy(pkg)
                p4["measurement"]["telemetry_before"] = copy.deepcopy(snap)
                recompute_all(vp, p4)
                v = forged(name, p4)
                if best is None or sum(v) > sum(best[0]):
                    best = (v, failed_names(p4))
            record("A4", name, best[0], best[1])
        req = request_of(pkg)
        if req["action"] == "goto" and pkg["decision"]["decision"] == "ALLOW":
            p5 = copy.deepcopy(pkg)
            req["params"]["lon_e7"] += EAST_100M_E7
            recompute_all(vp, p5, req)
            record("A5", name, forged(name, p5), failed_names(p5))

    print(f"corpus {len(corpus)} packages, latest {latest}")
    print(f"{'class':<8} {'n':>3}  {'D0':>6} {'D1':>6} {'D2':>6}   checks that refused under D0")
    summary = {}
    for cls in ("GENUINE", "A1", "A2", "A3", "A4", "A5", "A6", "A7"):
        rows = results.get(cls, [])
        n = len(rows)
        acc = {d: sum(r[d] for r in rows) for d in ("D0", "D1", "D2")}
        why = sorted({c for r in rows for c in r["failed"]})
        summary[cls] = dict(n=n, **acc)
        print(f"{cls:<8} {n:>3}  {acc['D0']:>3}/{n:<2} {acc['D1']:>3}/{n:<2} {acc['D2']:>3}/{n:<2}   {', '.join(why) or '-'}")

    s = summary
    preds = [
        ("P0", s["GENUINE"]["D0"] == s["GENUINE"]["n"] and s["GENUINE"]["D1"] == s["GENUINE"]["n"] and s["GENUINE"]["D2"] == 1),
        ("P1", s["A1"]["D0"] == s["A1"]["D1"] == s["A1"]["D2"] == 0),
        ("P2", s["A2"]["D0"] == 0),
        ("P3", s["A3"]["D0"] >= 1 and s["A3"]["D1"] == 0 and s["A3"]["D2"] == 0),
        ("P4", s["A4"]["D0"] >= 1 and s["A4"]["D1"] == 0 and s["A4"]["D2"] == 0),
        ("P5", s["A5"]["D0"] >= 1 and s["A5"]["D1"] == 0 and s["A5"]["D2"] == 0),
        ("P6", s["A6"]["D0"] == s["A6"]["n"] and s["A6"]["D1"] == s["A6"]["n"] and s["A6"]["D2"] == 0),
        ("P7", s["A7"]["D0"] == s["A7"]["D1"] == s["A7"]["D2"] == 1),
    ]
    for pid, ok in preds:
        print(f"{pid}  {'HELD' if ok else 'FAILED'}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"summary": summary, "rows": results, "predictions": dict(preds)}, fh, indent=1, sort_keys=True)
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if all(ok for _, ok in preds) else 1)


if __name__ == "__main__":
    main()
