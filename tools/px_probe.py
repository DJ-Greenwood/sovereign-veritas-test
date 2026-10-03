#!/usr/bin/env python3
"""px_probe.py - PX4 and PX2 (registered in docs/PX_PREREG.md): two of Perplexity's attacks
(docs/EXTERNAL_CRITIQUE_PERPLEXITY.md) tested against SV's own decision procedure and package format.

PX4  does a decision record say what would have changed it? Repair loop over all 4,690 contract vectors,
     on the kernel Gate and on the verifier's independent re-implementation.
PX2  is a change to a hard-coded rule (vehicle_check's 2 m altitude floor) visible in the package?
     Variants are COPIES of tools/vehicle_action.py and tools/verify_package.py, patched in a temp dir;
     the originals are never edited.

  python tools/px_probe.py              exit 0 iff the outcome is the recorded one
  python tools/px_probe.py --sabotage   PX4: a Gate that reports every failing rule; PX2: the check-source
                                        digest is recorded in the package (candidate fix). Outcome must differ.
Exit: 0 as recorded | 1 differs | 2 could not run.  Stdlib only.
"""
import argparse, copy, hashlib, importlib.util, json, os, re, subprocess, sys, tempfile

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


gc = load("gate_contract", os.path.join(ROOT, "tools", "gate_contract.py"))
from sovereign_veritas.evidence import canonical_json  # noqa: E402
from sovereign_veritas.package import sha256_hex  # noqa: E402


class CouldNotRun(Exception):
    pass


# ---------------------------------------------------------------------------------------------- PX4
def repair(inp, reason):
    """The registered repair table: one edit per reason type."""
    inp = copy.deepcopy(inp)
    rec, cap = inp["record"], inp["capability"]
    kind = reason.split(":")[0]
    if kind == "evidence_invalid":
        rec["input_digest"] = "a" * 64
    elif kind in ("verification_not_passed", "verification_refuted", "verification_insufficient_evidence"):
        rec["verification"] = {"status": "PASS"}
    elif kind == "capability_missing":
        name = (rec.get("action") or {}).get("capability") or "repaired"
        inp["capability"] = {"name": name, "authorized": True, "required_evidence": [], "parent": None,
                             "min_evidence_quality": None, "max_steps": None}
    elif kind == "capability_not_authorized":
        cap["authorized"] = True
    elif kind.startswith("capability_parent"):
        parent = cap["parent"]
        if not isinstance(inp["capability_registry"], dict):
            inp["capability_registry"] = {}
        inp["capability_registry"][parent] = {"name": parent, "authorized": True, "required_evidence": [],
                                              "parent": None, "min_evidence_quality": None, "max_steps": None}
    elif kind == "action_capability_mismatch":
        rec["action"] = dict(rec.get("action") or {}, capability=cap["name"])
    elif kind in ("runtime_state_unavailable", "runtime_not_healthy"):
        inp["runtime"] = {"thermal_status": "normal", "compute_budget": "available", "power_status": "stable"}
    elif kind == "missing_required_evidence":
        rec["metadata"] = dict(rec.get("metadata") or {}, **{reason.split(":", 1)[1]: True})
    elif kind in ("evidence_quality_below_threshold", "evidence_quality_invalid"):
        rec["evidence_quality"] = 1.0
        if "evidence_quality" in (rec.get("metadata") or {}):
            rec["metadata"] = dict(rec["metadata"], evidence_quality=1.0)
    elif kind in ("capability_max_steps_exceeded", "invalid_step_count_metadata"):
        rec["metadata"] = dict(rec.get("metadata") or {}, step_count=1)
    elif kind in ("policy_invalid", "action_not_permitted_by_policy"):
        requested = (rec.get("action") or {}).get("requested")
        old = inp["policy"].get("allow_only")
        inp["policy"] = dict(inp["policy"], allow_only=([requested] + (list(old) if isinstance(old, list) else [])))
    else:
        raise CouldNotRun(f"reason type outside the registered repair table: {reason}")
    return inp


def trajectory(decide, inp, rounds=13):
    """Repair every listed reason, re-decide; until ALLOW or the round limit."""
    steps = [decide(inp)]
    while steps[-1][0] != "ALLOW" and len(steps) <= rounds:
        for r in steps[-1][1]:
            inp = repair(inp, r)
        steps.append(decide(inp))
    return steps


def all_failures(decide):
    """SABOTAGE: a Gate that reports every failing rule (found by repairing and re-deciding), not only the first."""
    def d(inp):
        first = decide(inp)
        reasons, cur, out = list(first[1]), inp, decide(inp)
        while out[0] != "ALLOW" and out[1]:
            for r in out[1]:
                cur = repair(cur, r)
            out = decide(cur)
            reasons += [r for r in out[1] if r not in reasons]
        return first[0], reasons
    return d


def px4(sabotage):
    vectors = gc.read_vectors()
    kernel, verifier = gc.kernel_gate(), gc.verifier_gate()
    if sabotage:
        kernel, verifier = all_failures(kernel), all_failures(verifier)
    counts = {"REFUSE": 0, "DEFER": 0, "ALLOW": 0}
    masked = defer_complete = reached = disagree = allow_silent = 0
    max_rounds = 0
    for v in vectors:
        tk, tv = trajectory(kernel, v["input"]), trajectory(verifier, v["input"])
        first = tk[0][0]
        counts[first] += 1
        if tk != tv:
            disagree += 1
        if tk[-1][0] == "ALLOW":
            reached += 1
        max_rounds = max(max_rounds, len(tk) - 1)
        one = tk[1][0] if len(tk) > 1 else "ALLOW"
        if first == "REFUSE" and one != "ALLOW":
            masked += 1
        if first == "DEFER" and one == "ALLOW":
            defer_complete += 1
        if first == "ALLOW" and tk[0][1] == []:
            allow_silent += 1
    return {"vectors": len(vectors), "first_decisions": counts, "reach_allow": reached, "max_rounds": max_rounds,
            "refuse_masked": masked, "refuse_masked_pct": round(100.0 * masked / max(counts["REFUSE"], 1), 2),
            "defer_complete": defer_complete, "kernel_verifier_disagree": disagree, "allow_silent": allow_silent}


# ---------------------------------------------------------------------------------------------- PX2
FLOOR_CODE = "not 2 <= alt <= fence"
FLOOR_TEXT = "not within 2.."
DIGEST_LINE = '"thermal_before": [z.to_dict() for z in zones]}'


def patched_copy(src, dst, floor, sabotage=False):
    text = open(src, encoding="utf-8").read()
    if text.count(FLOOR_CODE) != 1 or text.count(FLOOR_TEXT) != 1:
        raise CouldNotRun(f"{src}: expected exactly one altitude-floor rule")
    text = text.replace(FLOOR_CODE, f"not {floor} <= alt <= fence").replace(FLOOR_TEXT, f"not within {floor}..")
    if sabotage and src.endswith("vehicle_action.py"):
        if text.count(DIGEST_LINE) != 1:
            raise CouldNotRun("cannot place the candidate check-source digest")
        text = text.replace(DIGEST_LINE, '"thermal_before": [z.to_dict() for z in zones], '
                                         '"check_source_sha256": hashlib.sha256(open(__file__, "rb").read()).hexdigest()}')
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return hashlib.sha256(text.encode()).hexdigest()


def make_package(tool, alt, home):
    env = dict(os.environ, HOME=home, USERPROFILE=home, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, tool, "--link", "fake:healthy_air", "--action", "goto", "--north", "50",
                          "--alt", str(alt), "--thermal-status", "normal"], env=env, capture_output=True, text=True,
                         check=False).stdout
    path = next((ln.split()[1] for ln in out.splitlines() if ln.startswith("package ")), None)
    if path is None:
        raise CouldNotRun(f"{tool} wrote no package: {out[-300:]}")
    with open(path, encoding="utf-8") as fh:
        return path, json.load(fh)


def verify(verifier, path):
    out = subprocess.run([sys.executable, verifier, path], capture_output=True, text=True, check=False,
                         env=dict(os.environ, PYTHONPATH=ROOT)).stdout
    failed = sorted(ln.split()[1] for ln in out.splitlines() if ln.startswith("FAIL"))
    verdict = next((ln.split()[1] for ln in out.splitlines() if ln.startswith("VERDICT")), "NONE")
    return verdict, failed


def px2(sabotage):
    work = tempfile.mkdtemp(prefix="px2-")
    va_src, vp_src = os.path.join(ROOT, "tools", "vehicle_action.py"), os.path.join(ROOT, "tools", "verify_package.py")
    tools, code_digests = {}, {}
    for name, floor in (("stock", 2), ("tight", 5), ("loose", 1)):
        d = os.path.join(work, name)
        os.makedirs(d)
        code_digests[name] = patched_copy(va_src, os.path.join(d, "vehicle_action.py"), floor, sabotage)
        patched_copy(vp_src, os.path.join(d, "verify_package.py"), floor)
        tools[name] = d
    stock_verifier = vp_src
    rows = {}
    for variant, alt in (("tight", 3.0), ("loose", 1.5)):
        home_s, home_v = tempfile.mkdtemp(dir=work), tempfile.mkdtemp(dir=work)
        ps, pkg_s = make_package(os.path.join(tools["stock"], "vehicle_action.py"), alt, home_s)
        pv, pkg_v = make_package(os.path.join(tools[variant], "vehicle_action.py"), alt, home_v)
        txt_v = json.dumps(pkg_v)
        version_fields = sum(dg in txt_v for dg in code_digests.values()) + \
            ("check_source_sha256" in pkg_v.get("measurement", {}))
        rows[variant] = {
            "alt": alt,
            "stock_decision": pkg_s["decision"]["decision"], "variant_decision": pkg_v["decision"]["decision"],
            "same_verifier_id": pkg_s["verifier_id"] == pkg_v["verifier_id"] if "verifier_id" in pkg_s else
            json.dumps(pkg_s).count("vehicle-command-check-v0") == txt_v.count("vehicle-command-check-v0"),
            "version_fields": version_fields,
            "variant_why": pkg_v["measurement"]["check"]["why"],
            "stock_verifier_on_variant": verify(stock_verifier, pv),
            "cochanged_verifier_on_variant": verify(os.path.join(tools[variant], "verify_package.py"), pv),
            "stock_verifier_on_stock": verify(stock_verifier, ps)[0],
        }
    return rows


def predictions(r4, r2):
    t, lo = r2["tight"], r2["loose"]
    px2d_detectable = t["version_fields"] + lo["version_fields"]
    return [
        ("PX4a repair loop reaches ALLOW for all 4,690 within 13 rounds",
         r4["reach_allow"] == r4["vectors"] == 4690 and r4["max_rounds"] <= 13,
         f"{r4['reach_allow']}/{r4['vectors']}, max rounds {r4['max_rounds']}"),
        ("PX4b repairing a REFUSE's listed reason misses ALLOW in >= 10% of REFUSE vectors",
         r4["refuse_masked_pct"] >= 10.0, f"{r4['refuse_masked']} of {r4['first_decisions']['REFUSE']} "
                                          f"({r4['refuse_masked_pct']}%)"),
        ("PX4c repairing a DEFER's listed reasons gives ALLOW in 59/59",
         r4["defer_complete"] == r4["first_decisions"]["DEFER"] == 59,
         f"{r4['defer_complete']} of {r4['first_decisions']['DEFER']}"),
        ("PX4d kernel and verifier trajectories identical on every vector", r4["kernel_verifier_disagree"] == 0,
         f"disagree {r4['kernel_verifier_disagree']}"),
        ("PX4e ALLOW vectors record no reasons (15/15)", r4["allow_silent"] == r4["first_decisions"]["ALLOW"] == 15,
         f"{r4['allow_silent']} of {r4['first_decisions']['ALLOW']}"),
        ("PX2a same verifier_id, 0 fields naming the check's code version",
         t["same_verifier_id"] and lo["same_verifier_id"] and px2d_detectable == 0,
         f"version fields tight {t['version_fields']} loose {lo['version_fields']}"),
        ("PX2b tight 'why' names the new floor; loose 'why' says all rules hold",
         "within 5.." in t["variant_why"] and lo["variant_why"] == "all goto rules hold" and "within" not in lo["variant_why"],
         f"tight: {t['variant_why'][:40]!r}; loose: {lo['variant_why']!r}"),
        ("PX2c stock verifier fails both variant packages",
         t["stock_verifier_on_variant"][0] != "CONSISTENT" and lo["stock_verifier_on_variant"][0] != "CONSISTENT"
         and t["stock_verifier_on_stock"] == lo["stock_verifier_on_stock"] == "CONSISTENT",
         f"tight {t['stock_verifier_on_variant']}, loose {lo['stock_verifier_on_variant']}"),
        ("PX2d co-changed verifier: both variants CONSISTENT, change undetectable from the packages",
         t["cochanged_verifier_on_variant"][0] == lo["cochanged_verifier_on_variant"][0] == "CONSISTENT"
         and px2d_detectable == 0,
         f"tight {t['cochanged_verifier_on_variant'][0]}, loose {lo['cochanged_verifier_on_variant'][0]}"),
    ]


RECORDED = ((True,) * 9,
            "dad7aee8ffe1224273d87b9b03ad12ea3f57adc937ea7d14d02fc922b831819c")  # pinned after the registered run (docs/PX_RESULTS.md)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sabotage", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    try:
        r4, r2 = px4(a.sabotage), px2(a.sabotage)
    except CouldNotRun as exc:
        print(f"COULD NOT RUN: {exc}")
        return 2
    print("PX4/PX2 | Perplexity attacks 4 and 2 | registered in docs/PX_PREREG.md")
    print("PX4 " + json.dumps(r4, sort_keys=True))
    for k, v in r2.items():
        print(f"PX2 {k} " + json.dumps(v, sort_keys=True))
    preds = predictions(r4, r2)
    held = [ok for _, ok, _ in preds]
    for name, ok, detail in preds:
        print(f"{'HELD' if ok else 'REFUTED':<8} {name:<86} {detail}")
    stable_r2 = {k: {x: y for x, y in v.items()} for k, v in r2.items()}
    dg = sha256_hex(canonical_json({"px4": r4, "px2": stable_r2, "held": held}).encode())
    print(f"VERDICT  {sum(held)} of {len(held)} as registered")
    print(f"DIGEST   {dg}")
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"px4": r4, "px2": r2, "held": held, "digest": dg}, fh, indent=1, sort_keys=True)
            fh.write("\n")
    if RECORDED is None:
        print("RECORDED none yet: first run")
        return 1
    same = (tuple(held), dg) == RECORDED
    print("OUTCOME  " + ("as recorded" if same else f"DIFFERS from the recorded {RECORDED}"))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
