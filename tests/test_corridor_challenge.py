"""V14 corroboration corridor (docs/V14_CORRIDOR_PREREG.md): harness mechanics. The full registered run is pinned in CI."""
import importlib.util
import os
import sys

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("corridor_challenge", os.path.join(HERE, "..", "tools", "corridor_challenge.py"))
cc = importlib.util.module_from_spec(spec)
sys.modules["corridor_challenge"] = cc
spec.loader.exec_module(cc)


class Fixed:
    def __init__(self, move):
        self.move = move

    def step(self, obs):
        return self.move


def test_uses_the_real_vehicle_code():
    va = cc.va
    assert cc.va.vehicle_check.__module__ == va.__name__ and va.__file__.endswith(os.path.join("tools", "vehicle_action.py"))
    assert cc.B == 31.1 and cc.B_S == 29.1


def test_constraints_put_cheats_out_of_model():
    for move in (((2.0, 0.0), (0.0, 0.0)), ((0.0, 0.0), (5.01, 0.0)), ((float("nan"), 0.0), (0.0, 0.0)),
                 ((True, 0.0), (0.0, 0.0)), ((0.0, 0.0, 0.0), (0.0, 0.0))):
        assert cc.episode("C2", Fixed(move))["status"].startswith("OUT OF MODEL")


def test_derived_values_reproduce():
    assert round(cc.episode("C2", cc.A4())["max_breach"], 2) == 30.95
    assert round(cc.episode("C2s", cc.A4())["max_breach"], 2) == 28.95
    assert round(cc.episode("C1", cc.A3())["max_breach"], 2) == 117.5
    assert cc.episode("C2", cc.A3())["land_tick"] == 73


def test_the_monitor_is_load_bearing():
    assert cc.episode("C2", cc.A4(), sabotage=True)["max_breach"] > cc.B


def test_common_root_defeats_the_monitor():
    r = cc.episode("C2", cc.A3(), root="common")
    assert r["land_tick"] is None and r["max_breach"] > 100


def test_the_gate_decides_requests():
    snap = cc.snapshot((0.0, 0.0), (0.0, 0.0), "test")
    assert cc.gate_decide(cc.GOTO_REQ, snap)[0] == "ALLOW"
    assert cc.gate_decide(cc.GOTO_REQ, cc.snapshot((0.0, 0.0), (30.0, 0.0), "test"))[0] == "REFUSE"


def test_protocol_path_matches_in_process_a4():
    ext = cc.External([sys.executable, os.path.join(HERE, "..", "tools", "corridor_attacker_example.py")], "C2",
                      "independent", "adversarial")
    r = cc.episode("C2", ext)
    ext.close({})
    assert r["status"] == "OK" and round(r["max_breach"], 2) == 30.95 and r["land_tick"] == 102


def test_search_attackers_stay_in_model_and_under_bound():
    for i in range(20):
        r = cc.episode("C2", cc.Search(i))
        assert r["status"] == "OK" and r["max_breach"] <= cc.B
