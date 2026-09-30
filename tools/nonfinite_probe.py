#!/usr/bin/env python3
"""Differential non-finite probe: the issue #5 bug class, searched for in every numeric field.

For every numeric field of a package, reseal three variants and verify each:
  - a large finite change (7v + 1001),
  - NaN, +Infinity, -Infinity.
A FAIL-OPEN is a field where the finite change FAILS but a non-finite value verifies CONSISTENT: the
check reads the field, and NaN/Infinity slip past it (issue #5: battery_pct = NaN passed a takeoff
check). A CRASH is any uncaught exception in the verifier. Reseal recomputes the digests the way an
attacker without the signing key can (a signed package would also need the key: this probes the
checks, not the signature).

  python tools/nonfinite_probe.py [package.json ...]     default: every package in evidence/
  python tools/nonfinite_probe.py --selftest              anti-vacuity: re-plants the 2026-09-30 bug

Exit 0 only if no FAIL-OPEN and no CRASH. Found on its first run (2026-09-30): failed_probes and
min_coverage fail-open, rounds = Infinity crash (fixed in verify_package.py the same day).
"""
import contextlib, copy, glob, importlib.util, io, json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_vp():
    s = importlib.util.spec_from_file_location("vp_probe", os.path.join(ROOT, "tools", "verify_package.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def reseal(vp, pkg):
    prev = None
    for e in pkg["provenance"]["chain"]:
        e["record"]["previous_digest"] = prev
        e["record_digest"] = prev = vp.sha(vp.canon(e["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def verify_rc(vp, pkg, path):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(pkg))
    old, sys.argv = sys.argv, ["verify_package.py", path]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                vp.main()
                return 0
            except SystemExit as e:
                return e.code
            except Exception as e:  # a crash is a finding, never a pass
                return "CRASH " + type(e).__name__
    finally:
        sys.argv = old


def leaves(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from leaves(v, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from leaves(v, path + (i,))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield path, o


def put(o, path, v):
    for k in path[:-1]:
        o = o[k]
    o[path[-1]] = v


def probe(vp, pkg, tmp):
    fail_open, crashes, n = [], [], 0
    for path, v in leaves(pkg):
        if path[0] == "package_sha256" or path[-1] in ("record_digest", "previous_digest"):
            continue
        n += 1
        fin = copy.deepcopy(pkg)
        put(fin, path, v * 7 + 1001)
        fin_rc = verify_rc(vp, reseal(vp, fin), tmp)
        for special in (float("nan"), float("inf"), float("-inf")):
            sp = copy.deepcopy(pkg)
            put(sp, path, special)
            rc = verify_rc(vp, reseal(vp, sp), tmp)
            name = ".".join(map(str, path)) + " = " + str(special)
            if isinstance(rc, str) or isinstance(fin_rc, str):
                crashes.append(name + f" ({rc if isinstance(rc, str) else fin_rc})")
            elif fin_rc != 0 and rc == 0:
                fail_open.append(name)
    return n, fail_open, crashes


def main():
    args = sys.argv[1:]
    vp = load_vp()
    tmp = os.path.join(tempfile.mkdtemp(prefix="sv_nonfinite_"), "probe.json")
    if args == ["--selftest"]:
        # re-plant the pre-fix rule; the probe must find it, or the probe is vacuous
        def old_rule(v):
            if v["failed_probes"] > 0:
                return "FAILED"
            total, mp, mpass = v["total_probes"], v["meaningful_probes"], v["meaningful_passes"]
            return "VALIDATED" if mp > 0 and mpass == mp and mp / total >= v["min_coverage"] else "UNTESTED"
        vp.validation_status = old_rule
        pkg = json.load(open(sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json")))[0]))
        _, fo, _ = probe(vp, pkg, tmp)
        ok = any("failed_probes" in f for f in fo)
        print(f"self-test: planted rule -> {len(fo)} FAIL-OPEN found ({'PASS' if ok else 'FAIL: the probe is vacuous'})")
        sys.exit(0 if ok else 1)
    files = args or sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json")))
    total_bad = 0
    for f in files:
        pkg = json.load(open(f))
        base = verify_rc(vp, reseal(vp, copy.deepcopy(pkg)), tmp)
        n, fo, cr = probe(vp, pkg, tmp)
        total_bad += len(fo) + len(cr)
        print(f"{os.path.basename(f)}: baseline exit {base}, {n} numeric fields x 3 non-finite values: "
              f"{len(fo)} FAIL-OPEN, {len(cr)} CRASH")
        for x in fo[:10] + cr[:10]:
            print("   ", x)
    print(f"VERDICT  {'no fail-open, no crash' if not total_bad else f'{total_bad} finding(s)'} over {len(files)} package(s)")
    sys.exit(1 if total_bad else 0)


if __name__ == "__main__":
    main()
