#!/usr/bin/env python3
"""corridor_challenge.py - V14, the corroboration corridor (registered in docs/V14_CORRIDOR_PREREG.md).

How far can a GNSS spoofer drive the vehicle outside its fence when the independent-position cross-check
runs only at request time (C1, today's tools/vehicle_action.py), or on every reading during the flight
(C2s single reading, C2 with the V13 latch, C2g as C2 but LAND holds position on GNSS)?

REAL CODE, imported, not copied: vehicle_check, distance_m, offset, DisagreementLatch from
tools/vehicle_action.py, and the Gate itself (EvidenceWorkflow) for every request decision.
MODEL, written for this experiment: the autopilot (perfect setpoint tracking), the sensors, the attacker
interface. It is a kinematic model, NOT an autopilot; see the registration for what that leaves out.

  python tools/corridor_challenge.py               every registered row; exit 0 iff the outcome is the recorded one
  python tools/corridor_challenge.py --sabotage    the monitor's LAND is never executed; the outcome must differ (exit 1)
  python tools/corridor_challenge.py --reference A4 --config C2 [--root common] [--noise adversarial] [--trace]
  python tools/corridor_challenge.py --attacker "python tools/corridor_attacker_example.py"
                                     [--config C2 --root independent --noise adversarial]   (the challenge)

Attacker protocol (any language), one JSON object per line:
  harness -> {"hello": "sv.corridor_attacker/0", "constants": {...}, "config": ..., "root": ..., "noise": ...}
  attacker -> {"ok": true}
  per tick: harness -> {"obs": {...}}   attacker -> {"g": [north_m, east_m], "e": [north_m, east_m]}
  end: harness -> {"bye": {"max_breach_m": ...}}, then stdin closes.
Exit: 0 recorded outcome / NO BREAK | 1 outcome differs / BREAK | 2 could not run | 3 OUT OF MODEL. Stdlib only.
"""
import argparse, hashlib, importlib.util, json, math, os, platform, queue, random, shlex, subprocess, sys, threading

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location("vehicle_action", os.path.join(ROOT, "tools", "vehicle_action.py"))
va = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("vehicle_action", va)
_spec.loader.exec_module(va)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal  # noqa: E402
from sovereign_veritas.package import sha256_hex  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

# ---- registered constants (docs/V14_CORRIDOR_PREREG.md) ---------------------------------------------
FENCE = {"lat_e7": 353632000, "lon_e7": -969270000, "radius_m": 300.0, "max_alt_m": 120.0}
R = FENCE["radius_m"]
TARGET = (299.0, 0.0)          # metres north, east of the fence centre
ALT = 20.0
L, K, RELEASE = 25.0, 3, 0.8   # cross-check limit (V12), latch (V13)
E, S, V = 5.0, 1.0, 5.0        # independent-source error bound, GNSS slew per tick, setpoint speed per tick
T_REQ, T_END, D_LAND = 40, 160, 30
Q = 0.1                        # allowance for integer-1e-7-degree positions (0.015 m in a gap) with margin
B = round((TARGET[0] - R) + L + E + (K - 1) * S + Q, 6)     # 31.1 m, C2
B_S = round((TARGET[0] - R) + L + E + Q, 6)                 # 29.1 m, C2s (k = 1)
TOL = 1e-9                     # float tolerance on the attacker constraints
CONFIGS = ("C1", "C2s", "C2", "C2g")
NOISES = ("adversarial", "uniform", "gauss10")
ROOTS = ("independent", "common")
CONSTANTS = {"R": R, "target": list(TARGET), "alt_m": ALT, "L": L, "k": K, "release": RELEASE, "E": E, "S": S,
             "v": V, "t_req": T_REQ, "T": T_END, "D_land": D_LAND, "B": B, "B_s": B_S}
SNAP_BASE = dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=85, rel_alt_mm=20000, armed=True,
                 mode="GUIDED")


class OutOfModel(Exception):
    """The attacker broke a constraint (slew S, error bound E, a non-finite number, the protocol)."""


class CouldNotRun(Exception):
    pass


# ---- geometry (plain floats: + - * / sqrt are correctly rounded everywhere) ------------------------
def norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def scale(a, k):
    return (a[0] * k, a[1] * k)


INWARD = (-1.0, 0.0)  # from the target (north) toward the centre: g along it pushes the true position outward


def is_num(x):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


# ---- requests and the real Gate -------------------------------------------------------------------
def request(action, with_limit):
    lim = {"min_fix_type": 3, "min_sats": 6, "min_battery_pct": 30}
    if with_limit:
        lim["max_nav_disagreement_m"] = L
    params = {"alt_m": ALT}
    if action == "goto":
        params["lat_e7"], params["lon_e7"] = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], *TARGET)
    return {"schema": va.REQUEST_SCHEMA, "action": action, "params": params, "fence": dict(FENCE), "limits": lim}


GOTO_REQ = request("goto", True)                       # what vehicle_action.py would send today
MON_LIMIT = {a: request(a, True) for a in ("takeoff", "goto")}      # C2s: the single-reading rule every tick
MON_NOLIMIT = {a: request(a, False) for a in ("takeoff", "goto")}   # C2/C2g: other rules; the latch does L


def snapshot(b, x, source):
    lat, lon = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], b[0], b[1])
    xl, xo = va.offset(FENCE["lat_e7"], FENCE["lon_e7"], x[0], x[1])
    return dict(SNAP_BASE, lat_e7=lat, lon_e7=lon, xpos_lat_e7=xl, xpos_lon_e7=xo, xpos_source=source)


class _NoEffect:
    """The flight is the model's job; the Gate's executor here only reports that it was called."""

    def execute(self, action):
        return {"reached": None}


def gate_decide(req, snap):
    """The real decision path of tools/vehicle_action.py main(), without the package: same verifier, probes,
    capability, policy and declared-normal thermal status as the V1-V13 runs."""
    artifact = canonical_json(req).encode("utf-8")
    predictor = va.RecordedSnapshot(snap, "corridor-model-not-a-vehicle")
    verifier = va.Check(req, snap, predictor.digest)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(va.VERIFIER_ID, verifier)
    probe_req = dict(req, action="goto", params={"alt_m": 20, "lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"]})
    good = va.FakeVehicle.SCENARIOS["healthy_air"] | {"lat_e7": FENCE["lat_e7"], "lon_e7": FENCE["lon_e7"],
                                                      "xpos_lat_e7": FENCE["lat_e7"], "xpos_lon_e7": FENCE["lon_e7"]}
    for s, want in ((good, "PASS"), (dict(good, gps_fix_type=0), "FAIL")):
        registry.record_probe(va.VERIFIER_ID, passed=va.vehicle_check(probe_req, s)["verdict"] == want)
    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"),
                                 metadata={"device": "corridor-model"}))
    wf = EvidenceWorkflow(sensor=va.Question(artifact), predictor=predictor, verifier=verifier,
                          executor=_NoEffect(), evidence_sink=LedgerSink(ledger), verifier_registry=registry)
    result = wf.run(record_id="corridor-request", input_digest=sha256_hex(artifact),
                    capability=Capability("vehicle_command", authorized=True, required_evidence=("verifier_probed",)),
                    runtime=RuntimeState(platform="corridor-model", python_version=platform.python_version(),
                                         thermal_status="normal", metadata={"thermal_status_source": "declared"}),
                    action=ActionProposal("vehicle_command", req["action"], req["params"]),
                    policy={"allow_only": ["takeoff", "goto", "land", "rtl"]},
                    metadata={"verifier_probed": True}, verifier_id=va.VERIFIER_ID)
    return result.decision.decision, list(result.decision.reasons)


# ---- honest noise ---------------------------------------------------------------------------------
def uniform_disk(rng, radius):
    r, th = radius * math.sqrt(rng.random()), 2 * math.pi * rng.random()
    return (r * math.cos(th), r * math.sin(th))


def gauss_pair(rng, sigma):
    u1, u2 = 1.0 - rng.random(), rng.random()  # u1 in (0, 1]
    r, th = sigma * math.sqrt(-2.0 * math.log(u1)), 2 * math.pi * u2
    return (r * math.cos(th), r * math.sin(th))


# ---- reference attackers (registered) -------------------------------------------------------------
def aligned(g):
    """e along g with length min(|g|, E): the gap |g - e| becomes |g| - E."""
    n = norm(g)
    return (0.0, 0.0) if n == 0 else scale(g, min(n, E) / n)


class A0:
    """Honest: no offset, no chosen error."""

    def step(self, obs):
        return (0.0, 0.0), (0.0, 0.0)


class A1:
    """Pre-request ramp, the V11/V12 attack inside the model: |g| = min(0.5 + t, 40), inward, aligned."""

    def step(self, obs):
        g = scale(INWARD, min(0.5 + obs["t"], 40.0))
        return g, aligned(g)


class A2:
    """The corridor: |g| = min(0.5 + t, L + E - 0.5 = 29.5), inward, aligned, held for the whole episode."""

    def step(self, obs):
        g = scale(INWARD, min(0.5 + obs["t"], L + E - 0.5))
        return g, aligned(g)


class A3:
    """Naive in-flight ramp: nothing until the ALLOW, then 0.5, 1.5, 2.5 ... m with no cap."""

    def __init__(self):
        self.start = None

    def step(self, obs):
        if self.start is None and obs["allowed"]:
            self.start = obs["t"]
        g = (0.0, 0.0) if self.start is None else scale(INWARD, 0.5 + (obs["t"] - self.start))
        return g, aligned(g)


class A4:
    """Threshold ride: after the ALLOW ramp to L + E - 0.05 = 29.95 m and hold; from the first tick after the
    setpoint has reached the target, add S per tick with no cap."""

    def __init__(self):
        self.start, self.m, self.pushing = None, 0.0, False

    def step(self, obs):
        if self.start is None and obs["allowed"]:
            self.start = obs["t"]
        if self.start is not None:
            sp = obs["setpoint_prev"]
            if not self.pushing and sp is not None and abs(sp[0] - TARGET[0]) < 1e-9 and abs(sp[1] - TARGET[1]) < 1e-9:
                self.pushing = True
            self.m = self.m + S if self.pushing else min(0.5 + (obs["t"] - self.start), L + E - 0.05)
        g = scale(INWARD, self.m)
        return g, aligned(g)


REFERENCE = {"A0": A0, "A1": A1, "A2": A2, "A3": A3, "A4": A4}


class Search:
    """One member of the registered search family, seeded by its index. Keeps itself inside S and E."""

    def __init__(self, i):
        r = random.Random(1_000_000 + i)
        self.t0 = r.randrange(0, T_END)
        self.rate = S * (0.05 + 0.95 * r.random())
        self.cap = 45.0 * r.random()
        ang = 0.0 if r.random() < 0.5 else 2 * math.pi * r.random()
        self.dir = (INWARD[0] * math.cos(ang) - INWARD[1] * math.sin(ang),
                    INWARD[0] * math.sin(ang) + INWARD[1] * math.cos(ang))
        self.perp = (-self.dir[1], self.dir[0])
        self.pulse = r.random() < 0.5
        self.pulse_every, self.pulse_len = r.randint(2, 10), r.randint(1, 3)
        self.wob_amp, self.wob_per = 3.0 * r.random(), r.randint(4, 20)
        self.e_mode = r.choices(("aligned", "random", "zero"), weights=(0.6, 0.2, 0.2))[0]
        self.rng = random.Random(2_000_000 + i)
        self.g = (0.0, 0.0)

    def step(self, obs):
        t = obs["t"]
        if t < self.t0:
            want = (0.0, 0.0)
        else:
            m = min(self.cap, self.rate * (t - self.t0 + 1))
            phase = (t - self.t0) % self.pulse_every
            if self.pulse and m >= self.cap and phase < self.pulse_len:
                m = self.cap + S * (phase + 1)  # over-run for pulse_len ticks, then fall back
            wob = self.wob_amp * math.sin(2 * math.pi * t / self.wob_per)
            want = add(scale(self.dir, m), scale(self.perp, wob))
        d = sub(want, self.g)
        n = norm(d)
        if n > 0.999 * S:
            d = scale(d, 0.999 * S / n)
        self.g = add(self.g, d)
        if self.e_mode == "aligned":
            n = norm(self.g)
            e = (0.0, 0.0) if n == 0 else scale(self.g, min(n, 0.999 * E) / n)
        elif self.e_mode == "random":
            e = uniform_disk(self.rng, 0.999 * E)
        else:
            e = (0.0, 0.0)
        return self.g, e


# ---- a challenger's program, isolated in its own process -------------------------------------------
class External:
    """Speaks the JSON-lines protocol to any program. It cannot touch this process's memory."""

    def __init__(self, cmd, config, root, noise, timeout=10.0):
        argv = cmd if isinstance(cmd, list) else shlex.split(cmd, posix=os.name != "nt")
        try:
            self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        except OSError as exc:
            raise CouldNotRun(f"cannot start attacker {argv!r}: {exc}")
        self.timeout, self.lines = timeout, queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()
        self._send({"hello": "sv.corridor_attacker/0", "constants": CONSTANTS, "config": config, "root": root,
                    "noise": noise})
        if self._recv().get("ok") is not True:
            raise OutOfModel("attacker did not answer the hello with {\"ok\": true}")

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _send(self, obj):
        try:
            self.proc.stdin.write(json.dumps(obj) + "\n")
            self.proc.stdin.flush()
        except OSError as exc:
            raise OutOfModel(f"attacker stopped reading: {exc}")

    def _recv(self):
        try:
            line = self.lines.get(timeout=self.timeout)
        except queue.Empty:
            raise OutOfModel(f"attacker gave no answer within {self.timeout} s")
        if line is None:
            raise OutOfModel("attacker exited")
        try:
            obj = json.loads(line)
        except ValueError:
            raise OutOfModel(f"attacker answer is not JSON: {line[:80]!r}")
        if not isinstance(obj, dict):
            raise OutOfModel("attacker answer is not a JSON object")
        return obj

    def step(self, obs):
        self._send({"obs": obs})
        r = self._recv()
        try:
            return tuple(r["g"]), tuple(r.get("e", (0.0, 0.0)))
        except (KeyError, TypeError) as exc:
            raise OutOfModel(f"attacker answer lacks g/e: {exc}")

    def close(self, summary):
        try:
            self._send({"bye": summary})
            self.proc.stdin.close()
        except (OutOfModel, OSError):
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def check_move(g, e, g_prev, noise):
    for v in (g, e):
        if not (isinstance(v, tuple) and len(v) == 2 and all(is_num(c) for c in v)):
            raise OutOfModel(f"not two finite numbers: {v!r}")
    g, e = (float(g[0]), float(g[1])), (float(e[0]), float(e[1]))
    if norm(sub(g, g_prev)) > S + TOL:
        raise OutOfModel(f"GNSS offset moved {norm(sub(g, g_prev)):.6f} m in one tick > S = {S} m")
    if noise == "adversarial" and norm(e) > E + TOL:
        raise OutOfModel(f"independent-source error {norm(e):.6f} m > E = {E} m")
    return g, e


# ---- one episode ----------------------------------------------------------------------------------
def setpoint(t, allowed):
    if not allowed:
        return (0.0, 0.0)  # hold over the take-off point, the fence centre
    return (min(TARGET[0], V * (t - T_REQ + 1)), 0.0)


def episode(config, attacker, noise="adversarial", root="independent", seed=0, sabotage=False, trace=None):
    """Run T_END ticks. Returns the decision, LAND tick, max breach and status (OK or OUT OF MODEL)."""
    rng = random.Random(seed)
    source = "model-common-root(x=gnss+e)" if root == "common" else "model-independent(x=true+e)"
    p, g_prev, e_prev, b_prev, x_prev, s_prev = (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), None, None, (0.0, 0.0)
    latch = va.DisagreementLatch(L, K, RELEASE) if config in ("C2", "C2g") else None
    decision, allowed, why, land_t, hold = None, None, "", None, None
    max_breach, worst_t, status, moves = 0.0, None, "OK", hashlib.sha256()
    for t in range(T_END):
        obs = {"t": t, "true": list(p), "believed_prev": b_prev and list(b_prev),
               "independent_prev": x_prev and list(x_prev), "g_prev": list(g_prev), "e_prev": list(e_prev),
               "setpoint_prev": s_prev and list(s_prev), "decision": decision, "allowed": allowed,
               "landing": land_t is not None, "land_tick": land_t,
               "latch": None if latch is None else {"over": latch.over, "under": latch.under, "latched": latch.latched}}
        try:
            g, e_att = check_move(*attacker.step(obs), g_prev, noise)
        except OutOfModel as exc:
            status = f"OUT OF MODEL at tick {t}: {exc}"
            break
        moves.update(f"{t} {g[0]!r} {g[1]!r} {e_att[0]!r} {e_att[1]!r}\n".encode())
        if noise == "adversarial":
            e = e_att
        elif noise == "uniform":
            e = uniform_disk(rng, E)
        else:
            e = gauss_pair(rng, 10.0)
        b = add(p, g)
        x = add(b, e) if root == "common" else add(p, e)
        snap = snapshot(b, x, source)
        if t == T_REQ:
            if land_t is not None:
                decision, why = "NONE", f"no request: LAND began at tick {land_t}"
            else:
                chk = va.vehicle_check(GOTO_REQ, snap)
                decision, reasons = gate_decide(GOTO_REQ, snap)
                if (decision == "ALLOW") != (chk["verdict"] == "PASS"):
                    raise CouldNotRun(f"the Gate said {decision} {reasons} on a check {chk['verdict']}")
                allowed, why = decision == "ALLOW", chk["why"]
        gap = va.distance_m(snap["lat_e7"], snap["lon_e7"], snap["xpos_lat_e7"], snap["xpos_lon_e7"])
        mon = None
        if config != "C1" and land_t is None:
            active = "goto" if allowed else "takeoff"
            if config == "C2s":
                mon = va.vehicle_check(MON_LIMIT[active], snap)["verdict"]
            else:
                rules = va.vehicle_check(MON_NOLIMIT[active], snap)["verdict"]
                mon = "FAIL" if (latch.update(gap) == "FAIL" or rules == "FAIL") else "PASS"
            if mon == "FAIL" and not sabotage:
                land_t, hold = t, b
        if land_t is None:
            s = setpoint(t, allowed)
            p_next = sub(s, g)              # perfect tracking: the believed position goes to the setpoint
        elif config == "C2g" and t < land_t + D_LAND:
            s = hold
            p_next = sub(hold, g)           # LAND holds the believed position: the vehicle follows g
        else:
            s = None
            p_next = p                      # LAND without position hold: no horizontal motion
        breach = max(0.0, norm(p_next) - R)
        if breach > max_breach:
            max_breach, worst_t = breach, t
        if trace is not None:
            trace.append(f"t {t:3d} |g| {norm(g):7.2f} |e| {norm(e):5.2f} gap {gap:7.2f} "
                         f"mon {mon or '-':4} dec {decision or '-':6} land {'-' if land_t is None else land_t!s:>3} "
                         f"setpoint {'-' if s is None else f'{s[0]:.1f},{s[1]:.1f}':>12} "
                         f"|p| {norm(p_next):7.2f} breach {breach:6.2f}")
        p, g_prev, e_prev, b_prev, x_prev, s_prev = p_next, g, e, b, x, s
    return {"decision": decision, "why": why, "land_tick": land_t, "max_breach": max_breach, "worst_tick": worst_t,
            "status": status, "moves_sha256": moves.hexdigest()}


# ---- the registered run ---------------------------------------------------------------------------
def summarise(results):
    n = len(results)
    ok = [r for r in results if r["status"] == "OK"]
    return {"runs": n, "allow": sum(r["decision"] == "ALLOW" for r in ok),
            "refuse": sum(r["decision"] == "REFUSE" for r in ok), "no_request": sum(r["decision"] == "NONE" for r in ok),
            "land": sum(r["land_tick"] is not None for r in ok), "out_of_model": n - len(ok),
            "max_breach_m": round(max((r["max_breach"] for r in ok), default=0.0), 2),
            "mean_breach_m": round(sum(r["max_breach"] for r in ok) / len(ok), 2) if ok else None}


def run_all(sabotage=False, progress=None):
    rows = {}

    def row(key, results, single=False):
        rows[key] = summarise(results)
        if single:
            r = results[0]
            rows[key].update(land_tick=r["land_tick"], why=r["why"], worst_tick=r["worst_tick"])

    for att in REFERENCE:
        for cfg in CONFIGS:
            row(f"{att}/adversarial/{cfg}/independent",
                [episode(cfg, REFERENCE[att](), "adversarial", "independent", sabotage=sabotage)], single=True)
    for att in ("A3", "A4"):
        row(f"{att}/adversarial/C2/common",
            [episode("C2", REFERENCE[att](), "adversarial", "common", sabotage=sabotage)], single=True)
    for cfg in CONFIGS:
        row(f"A0/uniform/{cfg}/independent",
            [episode(cfg, A0(), "uniform", "independent", seed=s, sabotage=sabotage) for s in range(200)])
    for cfg in ("C1", "C2s", "C2"):
        row(f"A0/gauss10/{cfg}/independent",
            [episode(cfg, A0(), "gauss10", "independent", seed=s, sabotage=sabotage) for s in range(200)])
    if progress:
        progress("reference rows done; running the 1,000-attacker search")
    search = [episode("C2", Search(i), "adversarial", "independent", sabotage=sabotage) for i in range(1000)]
    rows["search/adversarial/C2/independent"] = summarise(search)
    best = max(range(len(search)), key=lambda i: search[i]["max_breach"])
    rows["search/adversarial/C2/independent"].update(argmax=best)
    return rows


def predictions(rows):
    g = rows.get

    def near(x, want, tol=0.05):
        return x is not None and abs(x - want) <= tol

    a0u = [g(f"A0/uniform/{c}/independent") for c in CONFIGS]
    v14a_i = all(r["allow"] == 200 and r["land"] == 0 and r["max_breach_m"] == 0.0 for r in a0u)
    a1c1, a1c2 = g("A1/adversarial/C1/independent"), g("A1/adversarial/C2/independent")
    v14a_ii = (a1c1["refuse"] == 1 and "disagree" in a1c1["why"] and a1c1["max_breach_m"] == 0.0
               and a1c2["land"] == 1 and a1c2["no_request"] == 1 and a1c2["land_tick"] < T_REQ
               and a1c2["max_breach_m"] == 0.0)
    a2 = [g(f"A2/adversarial/{c}/independent") for c in ("C1", "C2")]
    v14b = all(r["allow"] == 1 and r["land"] == 0 and near(r["max_breach_m"], 28.5) for r in a2)
    a3c1, a3c2 = g("A3/adversarial/C1/independent"), g("A3/adversarial/C2/independent")
    v14c = (a3c1["allow"] == 1 and a3c1["max_breach_m"] >= 100.0
            and a3c2["land"] == 1 and a3c2["max_breach_m"] == 0.0)
    c2max = max(g(f"{a}/adversarial/C2/independent")["max_breach_m"] for a in REFERENCE)
    a4c2, a4c2s = g("A4/adversarial/C2/independent"), g("A4/adversarial/C2s/independent")
    v14d = c2max <= B and near(a4c2["max_breach_m"], 30.95) and near(a4c2s["max_breach_m"], 28.95)
    srch = g("search/adversarial/C2/independent")
    v14e = srch["max_breach_m"] <= B and srch["out_of_model"] == 0
    v14f = g("A4/adversarial/C2g/independent")["max_breach_m"] >= B + 20
    a3common = g("A3/adversarial/C2/common")
    v14g = a3common["land"] == 0 and a3common["max_breach_m"] >= 100.0
    gc1, gc2s, gc2 = (g(f"A0/gauss10/{c}/independent") for c in ("C1", "C2s", "C2"))
    v14h = gc2s["land"] >= 180 and gc2["land"] <= 10 and 2 <= gc1["refuse"] <= 20
    return [
        ("V14a anti-vacuity: honest ALLOW 200/200 no LAND 0 m; A1 refused (C1) / landed pre-request (C2)",
         v14a_i and v14a_ii,
         f"A0 allow {[r['allow'] for r in a0u]} land {[r['land'] for r in a0u]}; "
         f"A1 C1 {a1c1['refuse']} REFUSE ({a1c1['why'][:60]}), C2 LAND t={a1c2['land_tick']}"),
        ("V14b corridor A2: ALLOW, no LAND, 28.50 +-0.05 m in C1 and C2", v14b,
         f"C1 {a2[0]['max_breach_m']} m, C2 {a2[1]['max_breach_m']} m, LAND {[r['land'] for r in a2]}"),
        ("V14c A3: C1 ALLOW and >= 100 m; C2 LAND mid-flight, 0.00 m", v14c,
         f"C1 {a3c1['max_breach_m']} m; C2 LAND t={a3c2['land_tick']}, {a3c2['max_breach_m']} m"),
        (f"V14d bound: C2 refs <= B={B}; A4 C2 30.95, C2s 28.95 (+-0.05)", v14d,
         f"C2 max {c2max} m; A4 C2 {a4c2['max_breach_m']}, C2s {a4c2s['max_breach_m']}"),
        ("V14e search: 1,000 attackers in C2, none > B, none OUT OF MODEL", v14e,
         f"max {srch['max_breach_m']} m (attacker {srch['argmax']}), OOM {srch['out_of_model']}, LAND {srch['land']}"),
        (f"V14f C2g (LAND on GNSS), A4: >= B + 20 = {B + 20:.1f} m", v14f,
         f"{g('A4/adversarial/C2g/independent')['max_breach_m']} m"),
        ("V14g common root, A3 in C2: no LAND, >= 100 m", v14g,
         f"LAND {a3common['land']}, {a3common['max_breach_m']} m"),
        ("V14h gauss10 honest: C2s LAND >= 180, C2 <= 10, C1 REFUSE 2..20 (of 200)", v14h,
         f"C2s {gc2s['land']}, C2 {gc2['land']}, C1 REFUSE {gc1['refuse']}"),
    ]


def digest(rows, held):
    return sha256_hex(canonical_json({"rows": rows, "held": held}).encode("utf-8"))


# The outcome of the registered run, pinned after it (docs/V14_CORRIDOR_RESULTS.md). None = not yet run.
RECORDED = ((True, True, True, True, True, True, True, True),
            "4f09350ea05ee3d30ee9e2cd69c62d5fd459ddcb5984cd700c94509369afa665")


def main_registered(args):
    rows = run_all(sabotage=args.sabotage, progress=lambda m: print(m, flush=True))
    print(f"V14 corroboration corridor | B = {B} m (C2), B_s = {B_S} m (C2s) | registered in docs/V14_CORRIDOR_PREREG.md")
    print(f"{'attacker/noise/config/root':<38}{'runs':>5}{'allow':>6}{'refuse':>7}{'none':>5}{'land':>5}{'oom':>4}"
          f"{'max m':>9}{'mean m':>8}  land_t")
    for key, r in rows.items():
        print(f"{key:<38}{r['runs']:>5}{r['allow']:>6}{r['refuse']:>7}{r['no_request']:>5}{r['land']:>5}"
              f"{r['out_of_model']:>4}{r['max_breach_m']:>9.2f}{r['mean_breach_m']:>8.2f}  {r.get('land_tick', '')}")
    preds = predictions(rows)
    held = [ok for _, ok, _ in preds]
    for name, ok, detail in preds:
        print(f"{'HELD' if ok else 'REFUTED':<8} {name:<92} {detail}")
    d = digest(rows, held)
    print(f"VERDICT  {sum(held)} of {len(held)} as registered")
    print(f"DIGEST   {d}")
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"schema": "sv.corridor_results/0", "constants": CONSTANTS, "rows": rows,
                       "held": held, "digest": d}, fh, indent=1, sort_keys=True)
            fh.write("\n")
    if RECORDED is None:
        print("RECORDED none yet: this is the first run; pin the outcome above in RECORDED")
        return 1
    same = (tuple(held), d) == RECORDED
    print("OUTCOME  " + ("as recorded" if same else f"DIFFERS from the recorded {RECORDED}"))
    return 0 if same else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sabotage", action="store_true", help="never execute the monitor's LAND (the outcome must differ)")
    ap.add_argument("--reference", choices=sorted(REFERENCE), help="run one reference attacker")
    ap.add_argument("--attacker", help="a challenger's program (JSON-lines protocol), e.g. \"python my_attacker.py\"")
    ap.add_argument("--config", choices=CONFIGS, default="C2")
    ap.add_argument("--root", choices=ROOTS, default="independent")
    ap.add_argument("--noise", choices=NOISES, default="adversarial")
    ap.add_argument("--seed", type=int, default=0, help="honest-noise seed")
    ap.add_argument("--trace", action="store_true", help="print every tick")
    ap.add_argument("--json", help="write the registered run's results here")
    args = ap.parse_args()
    if not (args.reference or args.attacker):
        return main_registered(args)
    trace = [] if args.trace else None
    ext = None
    if args.attacker:
        ext = External(args.attacker, args.config, args.root, args.noise)
        attacker = ext
    else:
        attacker = REFERENCE[args.reference]()
    r = episode(args.config, attacker, args.noise, args.root, seed=args.seed, sabotage=args.sabotage, trace=trace)
    if ext:
        ext.close({"max_breach_m": round(r["max_breach"], 4), "status": r["status"]})
    for line in trace or ():
        print(line)
    who = args.attacker or args.reference
    print(f"attacker {who}  config {args.config}  root {args.root}  noise {args.noise}")
    print(f"request  {r['decision']}  {r['why']}")
    print(f"land     {'none' if r['land_tick'] is None else 'tick ' + str(r['land_tick'])}")
    print(f"breach   max {r['max_breach']:.4f} m at tick {r['worst_tick']}   moves sha256 {r['moves_sha256']}")
    if r["status"] != "OK":
        print(f"VERDICT  {r['status']} (not a breach)")
        return 3
    claim = args.config == "C2" and args.root == "independent" and args.noise == "adversarial" and not args.sabotage
    if not claim:
        print(f"VERDICT  max breach {r['max_breach']:.4f} m (the claim under challenge is C2, independent, adversarial)")
        return 0
    if r["max_breach"] > B:
        print(f"VERDICT  BREAK: max breach {r['max_breach']:.4f} m > B = {B} m")
        return 1
    print(f"VERDICT  NO BREAK: max breach {r['max_breach']:.4f} m <= B = {B} m")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CouldNotRun as exc:
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)
    except OutOfModel as exc:
        print(f"VERDICT  OUT OF MODEL: {exc} (not a breach)")
        sys.exit(3)
