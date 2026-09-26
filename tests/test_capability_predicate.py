"""Issue #4, B4: CapabilityRegistry.check() and the Gate must read authorization and evidence the
same way (identity, not truthiness). Registered in docs/ISSUE_4_RESPONSE.md as R1."""
import pytest

from sovereign_veritas.capability import Capability, CapabilityRegistry

AUTH = [True, 1, "yes", [1]]
EVIDENCE = [{"ok": True}, {"ok": 1}, {"ok": "FAILED"}, {"ok": [0]}, {"ok": False}, {}]


def gate_rule(authorized, evidence):
    """The Gate's rules 4 and 9 on one capability requiring 'ok' (sovereign_veritas/decision.py)."""
    return authorized is True and evidence.get("ok") is True


@pytest.mark.parametrize("authorized", AUTH)
@pytest.mark.parametrize("evidence", EVIDENCE)
def test_r1_check_agrees_with_the_gate(authorized, evidence):
    reg = CapabilityRegistry()
    reg.register(Capability("c", authorized=authorized, required_evidence=("ok",)))
    ok, _ = reg.check("c", evidence)
    assert ok is gate_rule(authorized, evidence)
    # not `evidence == {"ok": True}`: in Python {"ok": 1} == {"ok": True}, the very trap under test
    assert ok is (authorized is True and evidence.get("ok") is True)
