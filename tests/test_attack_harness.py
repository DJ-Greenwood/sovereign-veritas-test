"""The attack harness runs on the committed corpus and its registered predictions hold (docs/ATTACK_HARNESS.md)."""
import os, shutil, subprocess, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not installed")
def test_attack_harness_predictions_hold():
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "attack_harness.py"), "--round2"], capture_output=True, text=True,
                       timeout=300)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "GENUINE   21   21/21  21/21   1/21" in p.stdout  # anti-vacuity: acceptance is reportable
    assert "P11  HELD" in p.stdout  # the rollback gap is reported as a gap, not hidden
