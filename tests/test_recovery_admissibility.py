"""V15 (docs/V15_RECOVERY_PREREG.md): mechanics. The full registered outcome is pinned in CI."""
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("recovery_admissibility", os.path.join(os.path.dirname(__file__), "..", "tools", "recovery_admissibility.py"))
ra = importlib.util.module_from_spec(spec)
sys.modules["recovery_admissibility"] = ra
spec.loader.exec_module(ra)


def test_p0_is_the_real_check():
    snap, _ = ra.build_case("2")
    assert ra.va.vehicle_check(ra.request("rtl"), snap)["verdict"] == "FAIL"
    assert ra.p0("rtl", snap, None, False)[0] == "REFUSE"


def test_forger_without_key_breaks_the_mac():
    _, msg = ra.build_case("5f")
    assert ra.p2("rtl", ra.build_case("5f")[0], msg, False)[0] == "REFUSE"
    assert "MAC invalid" in ra.p2("rtl", ra.build_case("5f")[0], msg, False)[1]


def test_nonce_is_load_bearing():
    snap, msg = ra.build_case("5")
    assert ra.p2("rtl", snap, msg, False)[0] == "REFUSE"
    assert ra.p2("rtl", snap, msg, True)[0] == "ALLOW"


def test_derived_b_passes_even_authenticated():
    snap, msg = ra.build_case("4")
    assert ra.p2("rtl", snap, msg, False)[0] == "ALLOW"
