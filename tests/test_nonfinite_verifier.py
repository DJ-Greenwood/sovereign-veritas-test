"""Regression for 2026-09-30 (tools/nonfinite_probe.py): non-finite counts and chain rounds.

failed_probes = NaN or -Infinity used to verify CONSISTENT (the issue #5 class), and rounds = Infinity
crashed the verifier. Each case below fails on the pre-fix code and passes now."""
import copy, glob, importlib.util, json, os, time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("vp_nf", os.path.join(ROOT, "tools", "verify_package.py"))
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)
GOOD = {"failed_probes": 0, "total_probes": 4, "meaningful_probes": 4, "meaningful_passes": 4,
        "min_coverage": 0.5}


def test_valid_counts_still_validate():
    assert vp.validation_status(GOOD) == "VALIDATED"
    assert vp.validation_status(dict(GOOD, failed_probes=1)) == "FAILED"


@pytest.mark.parametrize("field,value", [
    ("failed_probes", float("nan")), ("failed_probes", float("-inf")), ("failed_probes", -1),
    ("failed_probes", 0.0), ("failed_probes", False), ("total_probes", float("inf")),
    ("meaningful_passes", 5), ("min_coverage", float("-inf")), ("min_coverage", float("nan")),
    ("min_coverage", 2), ("min_coverage", True),
])
def test_malformed_counts_never_validate(field, value):
    assert vp.validation_status(dict(GOOD, **{field: value})) == "MALFORMED"


@pytest.mark.parametrize("rounds", [float("inf"), float("-inf"), float("nan"), 10 ** 12, 0, -3, 2.0, True, "5"])
def test_chain_rounds_out_of_range_fail_fast_without_crashing(rounds):
    t = time.perf_counter()
    out = vp.recompute_measurement({"kind": "sha256_chain", "rounds": rounds}, b"x")
    assert isinstance(out, str) and "refused" in out
    assert time.perf_counter() - t < 1.0


def test_recorded_package_with_nan_failed_probes_fails_verification():
    pkg = json.load(open(sorted(glob.glob(os.path.join(ROOT, "evidence", "sv_package_*.json")))[0]))
    bad = copy.deepcopy(pkg)
    bad["verifier"]["validation"]["failed_probes"] = float("nan")
    names = [n for n, ok, _ in vp.verify(bad) if not ok]
    assert names, "a NaN failed_probes package must not verify"
