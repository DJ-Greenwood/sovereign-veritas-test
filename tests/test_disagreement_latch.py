import importlib.util
import os

spec = importlib.util.spec_from_file_location("va", os.path.join(os.path.dirname(__file__), "..", "tools", "vehicle_action.py"))
va = importlib.util.module_from_spec(spec)
spec.loader.exec_module(va)


def test_single_spike_does_not_latch():
    lt = va.DisagreementLatch(25.0)
    assert [lt.update(g) for g in (10, 30, 10, 30, 10)] == ["PASS"] * 5


def test_latches_after_three_and_releases_after_three_below_80_percent():
    lt = va.DisagreementLatch(25.0)
    out = [lt.update(g) for g in (26, 27, 28, 24, 21, 19, 19, 19)]
    assert out == ["PASS", "PASS", "FAIL", "FAIL", "FAIL", "FAIL", "FAIL", "PASS"]


def test_noise_at_threshold_does_not_flap():
    lt = va.DisagreementLatch(25.0)
    gaps = [24, 26, 23, 27, 24, 26, 28, 29, 30, 24, 26, 31]
    out = [lt.update(g) for g in gaps]
    assert out.count("FAIL") > 0 and "PASS" not in out[out.index("FAIL"):]
