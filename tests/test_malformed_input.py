"""Regression for 2026-09-30 (adversarial review of 595446c): malformed input crashed the verifier.

F1-F3 were uncaught tracebacks with exit 1, the same code as "checks failed". Malformed input is now
COULD NOT LOOK, exit 2. F4 (min_coverage = +-10**400) raised OverflowError inside math.isfinite; it now
recomputes to MALFORMED like NaN and +-Infinity do, so the package fails its checks (exit 1, no traceback).
Each case below fails on 595446c and passes now."""
import copy, glob, importlib.util, json, os, subprocess, sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VP = os.path.join(ROOT, "tools", "verify_package.py")
spec = importlib.util.spec_from_file_location("vp_mal", VP)
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)
GOOD = {"failed_probes": 0, "total_probes": 4, "meaningful_probes": 4, "meaningful_passes": 4,
        "min_coverage": 0.5}


def genuine():
    return json.load(open(sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json")))[0]))


def reseal(pkg):
    prev = None
    for e in pkg["provenance"]["chain"]:
        e["record"]["previous_digest"] = prev
        e["record_digest"] = prev = vp.sha(vp.canon(e["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def run(tmp_path, text):
    p = tmp_path / "pkg.json"
    p.write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, VP, str(p)], capture_output=True, text=True)
    assert "Traceback" not in r.stderr, r.stderr
    return r


@pytest.mark.parametrize("text", ["[]", "null", "1", '"x"'])
def test_f1_non_object_top_level_is_could_not_look(tmp_path, text):
    r = run(tmp_path, text)
    assert r.returncode == 2 and r.stdout.startswith("COULD NOT LOOK")


def test_f2_chain_as_string_is_could_not_look(tmp_path):
    pkg = genuine()
    pkg["provenance"]["chain"] = "x"
    r = run(tmp_path, json.dumps(pkg))
    assert r.returncode == 2 and r.stdout.startswith("COULD NOT LOOK")


@pytest.mark.parametrize("inside_package", [False, True])
def test_f3_deep_nesting_is_could_not_look(tmp_path, inside_package):
    deep = "[" * 100000 + "]" * 100000
    text = deep if not inside_package else json.dumps(genuine())[:-1] + ',"x":' + deep + "}"
    r = run(tmp_path, text)
    assert r.returncode == 2 and r.stdout.startswith("COULD NOT LOOK")


@pytest.mark.parametrize("value", [10 ** 400, -10 ** 400])
def test_f4_huge_integer_min_coverage_is_malformed_not_a_crash(tmp_path, value):
    assert vp.validation_status(dict(GOOD, min_coverage=value)) == "MALFORMED"
    pkg = genuine()
    pkg["verifier"]["validation"]["min_coverage"] = value
    r = run(tmp_path, json.dumps(reseal(pkg)))
    assert r.returncode == 1 and "FAIL" in r.stdout


@pytest.mark.parametrize("value", [0, 1, 0.5])
def test_f4_in_range_min_coverage_still_accepted(value):
    assert vp.validation_status(dict(GOOD, min_coverage=value)) == "VALIDATED"


@pytest.mark.parametrize("where,field", [("params", "alt_m"), ("telemetry", "battery_pct"), ("telemetry", "lat_e7")])
def test_f5_huge_integer_in_vehicle_request_or_telemetry_fails_not_crashes(tmp_path, where, field):
    """F5: vehicle_check -> is_finite_number -> math.isfinite(10**400) raised OverflowError. Forged with the
    attacker's best move (artifact, input and output digests recomputed, then resealed)."""
    import base64
    src = sorted(glob.glob(os.path.join(ROOT, "runs", "vehicle_sitl_v13", "*.json")))[0]
    pkg = json.load(open(src))
    rec, m = pkg["provenance"]["chain"][-1]["record"], pkg["measurement"]
    if where == "params":
        req = json.loads(base64.b64decode(pkg["artifact"]["bytes_b64"]))
        req.setdefault("params", {})[field] = 10 ** 400
        raw = json.dumps(req, sort_keys=True, separators=(",", ":")).encode()
        pkg["artifact"]["bytes_b64"] = base64.b64encode(raw).decode()
        pkg["artifact"]["sha256"] = m["artifact_sha256"] = rec["input_digest"] = vp.sha(raw)
        rec["action"]["parameters"] = req["params"]
    else:
        m["telemetry_before"][field] = 10 ** 400
        m["output_sha256"] = rec["prediction"]["value"]["output_sha256"] = vp.sha(vp.canon(m["telemetry_before"]))
    assert vp.is_finite_number(10 ** 400) is False
    r = run(tmp_path, json.dumps(reseal(pkg)))
    assert r.returncode == 1 and "FAIL" in r.stdout


# 2026-10-02: test_f3 failed on macOS + Python 3.14 only. That interpreter parsed the 100000-deep value
# (no RecursionError), so the verdict depended on the platform's C stack. The verifier now enforces its
# own depth limit (MAX_JSON_DEPTH). These cases sit far below any interpreter's recursion limit, so they
# exercise the verifier's rule, not the platform's.
@pytest.mark.parametrize("depth", [vp.MAX_JSON_DEPTH + 1, 200])
def test_f3b_depth_over_verifier_limit_is_could_not_look_on_every_platform(tmp_path, depth):
    deep = "[" * depth + "]" * depth
    text = json.dumps(genuine())[:-1] + ',"x":' + deep + "}"
    r = run(tmp_path, text)
    assert r.returncode == 2 and r.stdout.startswith("COULD NOT LOOK"), r.stdout
    assert "exceeds the verifier limit" in r.stdout


def test_f3b_depth_at_limit_is_parsed_and_judged(tmp_path):
    """Anti-vacuity: the limit must not refuse everything. Depth exactly at the limit parses; the extra
    key breaks the package digest, so the verdict is an ordinary check failure (exit 1)."""
    inner = vp.MAX_JSON_DEPTH - 1  # the package object itself is depth 1
    text = json.dumps(genuine())[:-1] + ',"x":' + "[" * inner + "]" * inner + "}"
    assert vp.json_depth(text) == vp.MAX_JSON_DEPTH
    r = run(tmp_path, text)
    assert r.returncode == 1 and "FAIL" in r.stdout, r.stdout


def test_json_depth_ignores_brackets_inside_strings():
    assert vp.json_depth('{"a": "[[[[{{{{", "b": "\\"]]]"}') == 1
    assert vp.json_depth('[[1, [2]], {"k": [3]}]') == 3
    assert vp.json_depth('"no containers"') == 0


def test_genuine_packages_are_well_inside_the_limit():
    for f in sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json"))):
        assert vp.json_depth(open(f, encoding="utf-8").read()) <= 16, f
