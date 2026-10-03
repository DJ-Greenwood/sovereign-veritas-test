"""PX4/PX2 (docs/PX_PREREG.md): repair-table mechanics. Full outcome pinned in CI."""
import importlib.util
import json
import os
import sys

spec = importlib.util.spec_from_file_location("px_probe", os.path.join(os.path.dirname(__file__), "..", "tools", "px_probe.py"))
px = importlib.util.module_from_spec(spec)
sys.modules["px_probe"] = px
spec.loader.exec_module(px)


def _vectors(n):
    with open(os.path.join(os.path.dirname(__file__), "..", "contract", "gate_vectors.jsonl"), encoding="utf-8") as fh:
        return [json.loads(next(fh)) for _ in range(n)]


def test_repair_loop_reaches_allow_and_kernel_matches_verifier():
    k, v = px.gc.kernel_gate(), px.gc.verifier_gate()
    for vec in _vectors(200):
        tk = px.trajectory(k, vec["input"])
        assert tk[-1][0] == "ALLOW" and tk == px.trajectory(v, vec["input"])


def test_unknown_reason_is_could_not_run():
    import pytest
    with pytest.raises(px.CouldNotRun):
        px.repair(_vectors(1)[0]["input"], "a_reason_nobody_registered")
