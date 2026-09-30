#!/usr/bin/env python3
"""The 30-second demo: make packages, verify them, tamper with them, time the verifier.

  python tools/demo_30s.py

Standard library only. Writes to a temporary directory, not your home. Exit 0 if every line below
comes out as expected, 1 otherwise (so the demo is itself a check that can fail).
"""
import copy, importlib.util, json, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_vp():
    s = importlib.util.spec_from_file_location("vp", os.path.join(ROOT, "tools", "verify_package.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def make(home, *args):
    env = dict(os.environ, HOME=home)
    before = set(os.listdir(home))
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_package.py"), *args],
                         env=env, capture_output=True, text=True)
    new = [f for f in os.listdir(home) if f not in before and f.endswith(".json")]
    return json.load(open(os.path.join(home, new[0]))) if new else None, out.stdout


def verify(path):
    t = time.perf_counter()
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "verify_package.py"), path],
                       capture_output=True, text=True)
    ms = 1000 * (time.perf_counter() - t)
    verdict = [ln for ln in p.stdout.splitlines() if ln.startswith("VERDICT")]
    fails = [ln.split()[1] for ln in p.stdout.splitlines() if ln.startswith("FAIL")]
    return p.returncode, (verdict[0] if verdict else p.stdout.strip()[:80]), fails, ms


def reseal(vp, pkg):
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def main():
    vp = load_vp()
    home = tempfile.mkdtemp(prefix="sv_demo_")
    ok = True

    def show(label, rc, verdict, fails, ms, want_rc):
        nonlocal ok
        good = rc == want_rc
        ok &= good
        extra = f"  failed: {', '.join(fails[:3])}" if fails else ""
        print(f"{'ok ' if good else 'BAD'} {label:<44} exit {rc}  {verdict}{extra}  ({ms:.0f} ms)")

    pkg, _ = make(home, "--thermal-status", "normal")
    print(f"    gate decision with a declared runtime state: {pkg['decision']['decision']}")
    path = os.path.join(home, "genuine.json")
    json.dump(pkg, open(path, "w"))
    show("1 genuine package", *verify(path), want_rc=0)

    ref, _ = make(home)
    d = ref["decision"]
    print(f"    gate decision with no runtime state:          {d['decision']} {d['reasons']}")
    ok &= d["decision"] == "REFUSE"

    t = copy.deepcopy(pkg)
    t["gate_inputs"]["policy"]["allow_only"].append("delete_everything")
    p2 = os.path.join(home, "edited.json")
    json.dump(t, open(p2, "w"))
    show("2 policy edited, not resealed", *verify(p2), want_rc=1)

    t = copy.deepcopy(pkg)
    t["gate_inputs"]["capability"]["authorized"] = False
    reseal(vp, t)
    p3 = os.path.join(home, "resealed.json")
    json.dump(t, open(p3, "w"))
    show("3 authorization revoked, digests resealed", *verify(p3), want_rc=1)

    times = [verify(path)[3] for _ in range(5)]
    print(f"    verifier wall time, genuine package, 5 runs (incl. Python start): "
          f"min {min(times):.0f} ms, max {max(times):.0f} ms")
    print("DEMO", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
