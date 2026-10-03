"""JG-1 (docs/JG1_PREREG.md): James Greenwood's five findings stay fixed; the probe can fail."""
import importlib.util
import os
import sys

spec = importlib.util.spec_from_file_location("jg1_probe", os.path.join(os.path.dirname(__file__), "..", "tools", "jg1_probe.py"))
jg = importlib.util.module_from_spec(spec)
sys.modules["jg1_probe"] = jg
spec.loader.exec_module(jg)


def test_registered_outcome_reproduces():
    obs = jg.run()
    assert all(ok for _, ok in obs.values()), {k: v[0] for k, v in obs.items() if not v[1]}


def test_unknown_thermal_or_budget_stops_search():
    from sovereign_veritas.adversarial import ResourcePolicy
    assert ResourcePolicy().branch_factor("Normal", "available") == 0
    assert ResourcePolicy().branch_factor("normal", None) == 0
