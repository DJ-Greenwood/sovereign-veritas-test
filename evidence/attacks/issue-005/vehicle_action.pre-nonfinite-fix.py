#!/usr/bin/env python3
"""vehicle_action.py - the Gate decides whether a flight command may be sent to a MAVLink autopilot.

One request per run. The request (the artifact) names an action and its parameters, a geofence and
navigation/battery limits. A telemetry snapshot is read from the vehicle; a deterministic check
compares request and snapshot; the Gate decides; only on ALLOW are MAVLink commands sent. The
package records the request, the snapshot, the check, the commands sent and the outcome;
tools/verify_package.py re-runs the check from the package alone. Registered in
docs/VEHICLE_ACTION.md.

This is a permission layer for a vehicle's own movement. It is not the vehicle's safety system
(the autopilot's failsafes act regardless) and it has no weapon, targeting or payload function.

  python tools/vehicle_action.py --action takeoff --alt 10
  python tools/vehicle_action.py --action goto --north 100 --east 0 --alt 20
  python tools/vehicle_action.py --action land
      [--link tcp:127.0.0.1:5760] [--fence-lat 35.3632 --fence-lon -96.9270 --fence-radius 300
       --ceiling 120] [--thermal-status measured|normal]
  python tools/vehicle_action.py --link fake:healthy_ground --action takeoff --alt 10

--link fake:SCENARIO is a canned stand-in, NOT a vehicle, for tests: healthy_ground, healthy_air,
gps_off, battery_low, outside_fence.
Exit: 0 a package was written, whatever the Gate decided | 2 could not run (no vehicle, no telemetry)
"""
import argparse, hashlib, json, math, os, platform, sys, time

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sovereign_veritas.capability import Capability  # noqa: E402
from sovereign_veritas.evidence import EvidenceRecord, Ledger, LedgerSink, canonical_json  # noqa: E402
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction  # noqa: E402
from sovereign_veritas.package import build_package, sha256_hex, write_package  # noqa: E402
from sovereign_veritas.runtime import RuntimeState  # noqa: E402
from sovereign_veritas.thermal import read_zones  # noqa: E402
from sovereign_veritas.thermal_policy import POLICY_ID, POLICIES, derive_thermal_status  # noqa: E402
from sovereign_veritas.verifier_registry import VerifierRegistry  # noqa: E402
from sovereign_veritas.workflow import EvidenceWorkflow  # noqa: E402

VERIFIER_ID = "vehicle-command-check-v0"
REQUEST_SCHEMA = "sv.vehicle_request/0"
MOVEMENT = ("takeoff", "goto")
EKF_POS_HORIZ_ABS = 16       # MAVLink ESTIMATOR_STATUS_FLAGS: absolute horizontal position valid
EKF_GPS_GLITCH = 32768       # ArduPilot: GPS glitching
EKF_UNINITIALIZED = 1024
EARTH_R = 6371000.0


def could_not_run(msg):
    print(f"COULD NOT RUN: {msg}")
    sys.exit(2)


# ---- the check (tools/verify_package.py re-implements it) -------------------------------------------
def distance_m(lat1_e7, lon1_e7, lat2_e7, lon2_e7):
    """Great-circle distance in metres between two points given in degrees * 1e7."""
    p1, p2 = math.radians(lat1_e7 / 1e7), math.radians(lat2_e7 / 1e7)
    dp, dl = p2 - p1, math.radians((lon2_e7 - lon1_e7) / 1e7)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


class DisagreementLatch:
    """V13: hysteresis on the independent-position cross-check, so one noisy reading cannot flip the verdict.
    Refuse once the disagreement has exceeded the limit on `k` consecutive readings; allow again only after
    it has been below `release` x limit on `k` consecutive readings. Pure and deterministic: feed it gaps."""

    def __init__(self, limit_m, k=3, release=0.8):
        self.limit, self.k, self.release = limit_m, k, release
        self.over = self.under = 0
        self.latched = False

    def update(self, gap_m):
        self.over = self.over + 1 if gap_m > self.limit else 0
        self.under = self.under + 1 if gap_m < self.release * self.limit else 0
        if not self.latched and self.over >= self.k:
            self.latched = True
        elif self.latched and self.under >= self.k:
            self.latched = False
        return "FAIL" if self.latched else "PASS"


def vehicle_check(req, snap):
    """PASS only if every rule for the action's class holds. Movement (takeoff, goto): fence, ceiling,
    navigation, battery. rtl: navigation only. land and every other action: no vehicle-state rule
    (land must never be refused for lost navigation; the policy decides which actions exist)."""
    action, p, fence, lim = req["action"], req.get("params") or {}, req["fence"], req["limits"]
    failures = []

    def nav():
        if snap["gps_fix_type"] < lim["min_fix_type"]:
            failures.append(f"gps fix {snap['gps_fix_type']} < {lim['min_fix_type']}")
        if snap["gps_sats"] < lim["min_sats"]:
            failures.append(f"satellites {snap['gps_sats']} < {lim['min_sats']}")
        flags = snap["ekf_flags"]
        if flags & EKF_UNINITIALIZED or not flags & EKF_POS_HORIZ_ABS:
            failures.append(f"ekf has no absolute horizontal position (flags {flags})")
        if flags & EKF_GPS_GLITCH:
            failures.append(f"ekf reports a gps glitch (flags {flags})")
        if "max_nav_disagreement_m" in lim:  # V12: cross-check against a position the spoofer does not control
            if not all(isinstance(snap.get(k), int) for k in ("xpos_lat_e7", "xpos_lon_e7")):
                failures.append("no independent position to cross-check")
            else:
                gap = distance_m(snap["lat_e7"], snap["lon_e7"], snap["xpos_lat_e7"], snap["xpos_lon_e7"])
                if gap > lim["max_nav_disagreement_m"]:
                    failures.append(f"autopilot and independent position disagree by {gap:.1f} m "
                                    f"> {lim['max_nav_disagreement_m']} m")

    if action in MOVEMENT:
        alt = p.get("alt_m")
        if isinstance(alt, bool) or not isinstance(alt, (int, float)) or not 2 <= alt <= fence["max_alt_m"]:
            failures.append(f"altitude {alt!r} not within 2..{fence['max_alt_m']} m")
        here = distance_m(fence["lat_e7"], fence["lon_e7"], snap["lat_e7"], snap["lon_e7"])
        if here > fence["radius_m"]:
            failures.append(f"vehicle {here:.1f} m from fence centre > {fence['radius_m']} m")
        if action == "goto":
            if not all(isinstance(p.get(k), int) and not isinstance(p.get(k), bool) for k in ("lat_e7", "lon_e7")):
                failures.append("goto target is not two integers (degrees * 1e7)")
            else:
                there = distance_m(fence["lat_e7"], fence["lon_e7"], p["lat_e7"], p["lon_e7"])
                if there > fence["radius_m"]:
                    failures.append(f"target {there:.1f} m from fence centre > {fence['radius_m']} m")
        nav()
        batt = snap["battery_pct"]
        if batt < 0:
            failures.append("battery remaining unknown")
        elif batt < lim["min_battery_pct"]:
            failures.append(f"battery {batt} % < {lim['min_battery_pct']} %")
    elif action == "rtl":
        nav()
    verdict = "FAIL" if failures else "PASS"
    return {"verdict": verdict, "why": "; ".join(failures) or f"all {action} rules hold", "failures": failures}


# ---- vehicles ---------------------------------------------------------------------------------------
SNAP_FIELDS = ("gps_fix_type", "gps_sats", "ekf_flags", "battery_pct", "lat_e7", "lon_e7",
               "rel_alt_mm", "armed", "mode")


class FakeVehicle:
    """A canned stand-in, NOT a vehicle: fixed telemetry, records commands, 'moves' instantly."""
    SCENARIOS = {
        "healthy_ground": dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=100, rel_alt_mm=0, armed=False, mode="STABILIZE"),
        "healthy_air": dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=90, rel_alt_mm=10000, armed=True, mode="GUIDED"),
        "gps_off": dict(gps_fix_type=0, gps_sats=0, ekf_flags=1024 | 167, battery_pct=90, rel_alt_mm=10000, armed=True, mode="GUIDED"),
        "battery_low": dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=12, rel_alt_mm=10000, armed=True, mode="GUIDED"),
        "outside_fence": dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=90, rel_alt_mm=10000, armed=True, mode="GUIDED"),
        "spoofed": dict(gps_fix_type=6, gps_sats=10, ekf_flags=831, battery_pct=90, rel_alt_mm=20000, armed=True, mode="GUIDED"),
    }

    def __init__(self, scenario, fence, xpos=False):
        if scenario not in self.SCENARIOS:
            could_not_run(f"unknown fake scenario {scenario!r}")
        s = dict(self.SCENARIOS[scenario])
        s["lat_e7"], s["lon_e7"] = fence["lat_e7"], fence["lon_e7"]
        if scenario == "outside_fence":
            s["lat_e7"] += 45000  # about 500 m north
        if xpos:  # the independent position: where the vehicle is; in "spoofed", 111 m north of its belief
            s["xpos_lat_e7"], s["xpos_lon_e7"] = s["lat_e7"] + (10000 if scenario == "spoofed" else 0), s["lon_e7"]
            s["xpos_source"] = "fake-stand-in"
        self.state, self.name, self.commands = s, "fake-stand-in-not-a-vehicle", []

    def snapshot(self):
        return dict(self.state)

    def run(self, action, params):
        self.commands.append(f"{action} {canonical_json(params)}")
        if action == "takeoff":
            self.state.update(armed=True, mode="GUIDED", rel_alt_mm=int(params["alt_m"] * 1000))
        elif action == "goto":
            self.state.update(lat_e7=params["lat_e7"], lon_e7=params["lon_e7"], rel_alt_mm=int(params["alt_m"] * 1000))
        elif action in ("land", "rtl"):
            self.state.update(armed=False, rel_alt_mm=0, mode=action.upper())
        return True


class MavlinkVehicle:
    """Any MAVLink autopilot; tested against ArduCopter SITL only."""

    def __init__(self, link, timeout_s, xpos_sigma=None):
        try:
            from pymavlink import mavutil
        except ImportError:
            could_not_run("pymavlink is not installed (pip install pymavlink)")
        self.mavutil, self.timeout_s, self.commands = mavutil, timeout_s, []
        try:
            self.m = mavutil.mavlink_connection(link, source_system=250, autoreconnect=False)
            hb = self.m.wait_heartbeat(timeout=15)
        except Exception as exc:  # noqa: BLE001 - any connection failure is could-not-run
            could_not_run(f"no vehicle at {link} ({exc})")
        if hb is None:
            could_not_run(f"no heartbeat from {link}")
        self.name = f"mavlink autopilot {hb.autopilot} type {hb.type} sysid {self.m.target_system}"
        self.m.mav.request_data_stream_send(self.m.target_system, self.m.target_component,
                                            mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
        self.last = {}
        self.xpos_sigma = xpos_sigma
        import random
        self.rng = random.SystemRandom()

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            msg = self.m.recv_match(blocking=True, timeout=0.2)
            if msg is None:
                continue
            t = msg.get_type()
            if t == "HEARTBEAT" and msg.get_srcSystem() != self.m.target_system:
                continue
            if t in ("GPS_RAW_INT", "EKF_STATUS_REPORT", "SYS_STATUS", "GLOBAL_POSITION_INT", "HEARTBEAT", "STATUSTEXT",
                     "SIMSTATE"):
                self.last[t] = msg

    def snapshot(self):
        need = ("GPS_RAW_INT", "EKF_STATUS_REPORT", "SYS_STATUS", "GLOBAL_POSITION_INT", "HEARTBEAT")
        if self.xpos_sigma is not None:
            need += ("SIMSTATE",)
        self.last = {}
        end = time.time() + 15
        while time.time() < end and not all(k in self.last for k in need):
            self.pump(0.5)
        missing = [k for k in need if k not in self.last]
        if missing:
            could_not_run(f"no telemetry for {missing}")
        g, e, s, pos, hb = (self.last[k] for k in need[:5])
        mode = self.mavutil.mode_string_v10(hb)
        snap = {"gps_fix_type": int(g.fix_type), "gps_sats": int(g.satellites_visible), "ekf_flags": int(e.flags),
                "battery_pct": int(s.battery_remaining), "lat_e7": int(pos.lat), "lon_e7": int(pos.lon),
                "rel_alt_mm": int(pos.relative_alt),
                "armed": bool(hb.base_mode & self.mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED), "mode": mode}
        if self.xpos_sigma is not None:
            # STAND-IN, NOT A SENSOR: SITL's true position plus Gaussian noise (docs/VEHICLE_ACTION.md, V12).
            t, sg = self.last["SIMSTATE"], self.xpos_sigma
            dn, de = self.rng.gauss(0, sg), self.rng.gauss(0, sg)
            snap["xpos_lat_e7"], snap["xpos_lon_e7"] = offset(int(t.lat), int(t.lng), dn, de)
            snap["xpos_source"] = f"sitl-truth+noise(sigma={sg:g}m)"
        return snap

    def _mode(self, name):
        self.m.set_mode(name)
        self.commands.append(f"SET_MODE {name}")

    def _wait(self, ok, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.pump(0.5)
            if ok():
                return True
        return False

    def _armed(self):
        hb = self.last.get("HEARTBEAT")
        return bool(hb and hb.base_mode & self.mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

    def _alt(self):
        p = self.last.get("GLOBAL_POSITION_INT")
        return None if p is None else p.relative_alt / 1000.0

    def run(self, action, params):
        mav, t = self.m.mav, self.timeout_s
        if action == "takeoff":
            self._mode("GUIDED")
            for _ in range(10):  # pre-arm checks may still be settling
                self.m.arducopter_arm()
                self.commands.append("ARM")
                if self._wait(self._armed, 5):
                    break
            if not self._armed():
                return False
            mav.command_long_send(self.m.target_system, self.m.target_component,
                                  self.mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, params["alt_m"])
            self.commands.append(f"NAV_TAKEOFF {params['alt_m']}")
            return self._wait(lambda: (self._alt() or 0) >= 0.9 * params["alt_m"], t)
        if action == "goto":
            self._mode("GUIDED")
            mav.set_position_target_global_int_send(
                0, self.m.target_system, self.m.target_component,
                self.mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT, 0b0000111111111000,
                params["lat_e7"], params["lon_e7"], params["alt_m"], 0, 0, 0, 0, 0, 0, 0, 0)
            self.commands.append(f"SET_POSITION_TARGET_GLOBAL_INT {params['lat_e7']} {params['lon_e7']} {params['alt_m']}")

            def there():
                p = self.last.get("GLOBAL_POSITION_INT")
                return p is not None and distance_m(p.lat, p.lon, params["lat_e7"], params["lon_e7"]) <= 3.0 \
                    and abs(p.relative_alt / 1000.0 - params["alt_m"]) <= 1.5
            return self._wait(there, t)
        if action in ("land", "rtl"):
            self._mode(action.upper())
            return self._wait(lambda: not self._armed(), t)
        return False  # the policy refuses every other action; nothing is sent


# ---- workflow pieces ----------------------------------------------------------------------------------
class Question:
    def __init__(self, data):
        self.data = data

    def observe(self):
        return self.data


class RecordedSnapshot:
    def __init__(self, snap, name):
        self.digest, self.name = sha256_hex(canonical_json(snap).encode("utf-8")), name

    def predict(self, observation):
        return Prediction(value={"output_sha256": self.digest}, model_id=self.name)


class Check:
    def __init__(self, req, snap, digest):
        self.req, self.snap, self.digest = req, snap, digest

    def verify(self, observation, prediction):
        if prediction.value.get("output_sha256") != self.digest:
            return {"status": "FAIL"}
        return {"status": vehicle_check(self.req, self.snap)["verdict"]}


class Execute:
    def __init__(self, vehicle):
        self.vehicle = vehicle

    def execute(self, action):
        reached = self.vehicle.run(action.requested, action.parameters)
        return {"reached": bool(reached)}


def offset(lat_e7, lon_e7, north_m, east_m):
    dlat = north_m / EARTH_R
    dlon = east_m / (EARTH_R * math.cos(math.radians(lat_e7 / 1e7)))
    return int(round(lat_e7 + math.degrees(dlat) * 1e7)), int(round(lon_e7 + math.degrees(dlon) * 1e7))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True)
    ap.add_argument("--alt", type=float, default=None)
    ap.add_argument("--north", type=float, default=0.0, help="goto target, metres north of the fence centre")
    ap.add_argument("--east", type=float, default=0.0)
    ap.add_argument("--link", default="tcp:127.0.0.1:5760")
    ap.add_argument("--fence-lat", type=float, default=35.3632)
    ap.add_argument("--fence-lon", type=float, default=-96.9270)
    ap.add_argument("--fence-radius", type=float, default=300.0)
    ap.add_argument("--ceiling", type=float, default=120.0)
    ap.add_argument("--min-fix", type=int, default=3)
    ap.add_argument("--min-sats", type=int, default=6)
    ap.add_argument("--min-battery", type=int, default=30)
    ap.add_argument("--max-disagreement", type=float, default=None,
                    help="metres; require an independent position within this distance of the autopilot's (V12)")
    ap.add_argument("--xpos-sigma", type=float, default=None,
                    help="SITL only: read an independent position as true position + N(0, sigma) m, a stand-in")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--thermal-status", default="measured")
    ap.add_argument("--thermal-root", default="/sys/class/thermal")
    a = ap.parse_args()

    fence = {"lat_e7": int(round(a.fence_lat * 1e7)), "lon_e7": int(round(a.fence_lon * 1e7)),
             "radius_m": a.fence_radius, "max_alt_m": a.ceiling}
    params = {}
    if a.action in ("takeoff", "goto"):
        if a.alt is None:
            could_not_run(f"{a.action} needs --alt")
        params["alt_m"] = a.alt
    if a.action == "goto":
        params["lat_e7"], params["lon_e7"] = offset(fence["lat_e7"], fence["lon_e7"], a.north, a.east)
    req = {"schema": REQUEST_SCHEMA, "action": a.action, "params": params, "fence": fence,
           "limits": {"min_fix_type": a.min_fix, "min_sats": a.min_sats, "min_battery_pct": a.min_battery}}
    if a.max_disagreement is not None:
        req["limits"]["max_nav_disagreement_m"] = a.max_disagreement
    artifact = canonical_json(req).encode("utf-8")

    if a.link.startswith("fake:"):
        vehicle, backend = FakeVehicle(a.link[5:], fence, xpos=a.xpos_sigma is not None), "fake"
    else:
        vehicle, backend = MavlinkVehicle(a.link, a.timeout, a.xpos_sigma), "mavlink"
    zones = read_zones(a.thermal_root)
    snap = vehicle.snapshot()
    chk = vehicle_check(req, snap)

    if a.thermal_status == "measured":
        thermal_status, why = derive_thermal_status([z.to_dict() for z in zones], POLICIES[POLICY_ID])
        meta, thermal_state = {"thermal_status_source": "measured", "thermal_policy": POLICY_ID}, "DERIVED"
    else:
        thermal_status, why = a.thermal_status, "declared"
        meta, thermal_state = {"thermal_status_source": "declared"}, "OPERATOR"

    predictor = RecordedSnapshot(snap, vehicle.name)
    verifier = Check(req, snap, predictor.digest)
    registry = VerifierRegistry(min_coverage=0.5)
    registry.register(VERIFIER_ID, verifier)
    probe_req = dict(req, action="goto", params={"alt_m": 20, "lat_e7": fence["lat_e7"], "lon_e7": fence["lon_e7"]})
    good = FakeVehicle.SCENARIOS["healthy_air"] | {"lat_e7": fence["lat_e7"], "lon_e7": fence["lon_e7"],
                                                   "xpos_lat_e7": fence["lat_e7"], "xpos_lon_e7": fence["lon_e7"]}
    for s, want in ((good, "PASS"), (dict(good, gps_fix_type=0), "FAIL")):  # the check must be able to fail
        registry.record_probe(VERIFIER_ID, passed=vehicle_check(probe_req, s)["verdict"] == want)

    ledger = Ledger()
    ledger.append(EvidenceRecord(record_id="session-start", input_digest=sha256_hex(b"session"),
                                 metadata={"device": platform.machine(), "python": platform.python_version()}))
    capability = Capability("vehicle_command", authorized=True, required_evidence=("verifier_probed",))
    runtime = RuntimeState(platform=platform.platform(), python_version=platform.python_version(),
                           thermal_status=thermal_status, metadata=meta)
    policy = {"allow_only": ["takeoff", "goto", "land", "rtl"]}
    action = ActionProposal("vehicle_command", a.action, params)
    wf = EvidenceWorkflow(sensor=Question(artifact), predictor=predictor, verifier=verifier,
                          executor=Execute(vehicle), evidence_sink=LedgerSink(ledger), verifier_registry=registry)
    result = wf.run(record_id="vehicle-action-1", input_digest=sha256_hex(artifact), capability=capability,
                    runtime=runtime, action=action, policy=policy, metadata={"verifier_probed": True},
                    verifier_id=VERIFIER_ID)
    ran = result.executed
    after = vehicle.snapshot()  # always: a refusal must also show the vehicle was left alone

    measurement = {"kind": "vehicle_command_check", "artifact_sha256": sha256_hex(artifact), "backend": backend,
                   "vehicle": vehicle.name, "telemetry_before": snap, "output_sha256": predictor.digest,
                   "check": chk, "commands_sent": list(vehicle.commands),
                   "outcome": {"reached": result.execution_result["reached"]} if ran else None,
                   "telemetry_after": after,
                   "thermal_before": [z.to_dict() for z in zones]}
    pkg = build_package(artifact=artifact, artifact_name=f"vehicle_request:{a.action}", measurement=measurement,
                        chain=ledger.all(), capability=capability, runtime=runtime, policy=policy,
                        verifier_id=VERIFIER_ID, validation=registry.validation(VERIFIER_ID),
                        thermal=read_zones(a.thermal_root),
                        evidence_states={"thermal_status": thermal_state, "compute_budget": "DEFAULTED",
                                         "power_status": "DEFAULTED"})
    path = write_package(pkg, os.path.expanduser("~"))
    print(f"backend {backend}  vehicle {vehicle.name}  action {a.action} {canonical_json(params)}")
    print(f"before  fix {snap['gps_fix_type']} sats {snap['gps_sats']} ekf {snap['ekf_flags']} battery {snap['battery_pct']}% "
          f"alt {snap['rel_alt_mm'] / 1000:.1f} m armed {snap['armed']} mode {snap['mode']}")
    print(f"check   {chk['verdict']} ({chk['why']})")
    print(f"thermal {thermal_status} ({why})")
    print(f"decision {pkg['decision']['decision']} {pkg['decision']['reasons']}")
    print(f"sent    {vehicle.commands or 'nothing'}")
    moved = distance_m(snap["lat_e7"], snap["lon_e7"], after["lat_e7"], after["lon_e7"])
    print(f"after   reached {measurement['outcome']['reached'] if ran else None}  alt {after['rel_alt_mm'] / 1000:.1f} m "
          f"moved {moved:.1f} m armed {after['armed']} mode {after['mode']}")
    print(f"package {path}  md5 {hashlib.md5(canonical_json(pkg).encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
