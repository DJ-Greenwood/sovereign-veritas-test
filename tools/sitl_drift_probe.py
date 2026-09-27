#!/usr/bin/env python3
"""sitl_drift_probe.py - ArduPilot SITL only: ramp a slow GPS position offset (SIM_GPS1_GLTCH_X) and
report the TRUE position (SIMSTATE, which a real vehicle does not have) against the believed one.
Used for V11 in docs/VEHICLE_ACTION.md. Fence centre hard-coded to the default 35.3632, -96.9270.

  python tools/sitl_drift_probe.py ramp        # 100 steps of 0.00001 deg, one per second
  python tools/sitl_drift_probe.py ramp-check  # the same ramp, running the vehicle check at every step
                                               # (V12c: independent position = truth + N(0, 3 m))
  python tools/sitl_drift_probe.py LABEL       # report once
"""
import sys, time, math
from pymavlink import mavutil
FLAT, FLON = 353632000, -969270000
def d(a, b, c, e):
    p1, p2 = math.radians(a/1e7), math.radians(c/1e7); dp = p2-p1; dl = math.radians((e-b)/1e7)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*6371000*math.asin(math.sqrt(x))
m = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=253); m.wait_heartbeat(timeout=20)
m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
last = {}
def pump(s):
    end = time.time()+s
    while time.time() < end:
        x = m.recv_match(blocking=True, timeout=0.2)
        if x: last[x.get_type()] = x
def report(tag):
    t, g, e = last.get("SIMSTATE"), last.get("GLOBAL_POSITION_INT"), last.get("EKF_STATUS_REPORT")
    print(f"{tag}: true {d(FLAT,FLON,t.lat,t.lng):.1f} m from fence centre, believed {d(FLAT,FLON,g.lat,g.lon):.1f} m, "
          f"true-vs-believed {d(t.lat,t.lng,g.lat,g.lon):.1f} m, ekf {e.flags}", flush=True)
mode = sys.argv[1]
pump(2)
if mode in ("ramp-check", "ramp-check-v13"):
    import importlib.util, os, random
    spec = importlib.util.spec_from_file_location("va", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicle_action.py"))
    va = importlib.util.module_from_spec(spec); spec.loader.exec_module(va)
    fence = {"lat_e7": FLAT, "lon_e7": FLON, "radius_m": 300.0, "max_alt_m": 120.0}
    req = {"schema": va.REQUEST_SCHEMA, "action": "goto", "fence": fence,
           "params": {"alt_m": 20.0, "lat_e7": FLAT, "lon_e7": FLON},
           "limits": {"min_fix_type": 3, "min_sats": 6, "min_battery_pct": 30, "max_nav_disagreement_m": 25.0}}
    rng, first = random.SystemRandom(), None
    latch, verdicts, latched_v = va.DisagreementLatch(25.0), [], []
    for i in range(0, 101):
        if i:
            m.mav.param_set_send(m.target_system, m.target_component, b"SIM_GPS1_GLTCH_X", i*0.00001, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        pump(1.0)
        t, g, e, gr, ss = (last[k] for k in ("SIMSTATE", "GLOBAL_POSITION_INT", "EKF_STATUS_REPORT", "GPS_RAW_INT", "SYS_STATUS"))
        xl, xo = va.offset(int(t.lat), int(t.lng), rng.gauss(0, 3), rng.gauss(0, 3))
        snap = {"gps_fix_type": gr.fix_type, "gps_sats": gr.satellites_visible, "ekf_flags": e.flags,
                "battery_pct": ss.battery_remaining, "lat_e7": g.lat, "lon_e7": g.lon, "rel_alt_mm": g.relative_alt,
                "armed": True, "mode": "GUIDED", "xpos_lat_e7": xl, "xpos_lon_e7": xo}
        chk = va.vehicle_check(req, snap)
        gap = va.distance_m(g.lat, g.lon, xl, xo)
        verdicts.append(chk["verdict"]); latched_v.append(latch.update(gap))
        if mode == "ramp-check-v13" and i % 5 == 0:
            print(f"step {i:3d}: gap {gap:6.1f} m  single-reading {chk['verdict']}  latched {latched_v[-1]}", flush=True)
        if chk["verdict"] == "FAIL" and first is None:
            first = i
            print(f"first FAIL at step {i} (offset {i*0.00001:.5f} deg): {chk['why']}", flush=True)
        if i % 10 == 0:
            print(f"step {i:3d}: {chk['verdict']}  {chk['why'][:90]}", flush=True)
    print("first failing step:", first)
    if mode == "ramp-check-v13":
        flips = lambda v: (sum(1 for a, b in zip(v, v[1:]) if a == "PASS" and b == "FAIL"),  # noqa: E731
                           sum(1 for a, b in zip(v, v[1:]) if a == "FAIL" and b == "PASS"))
        print(f"single-reading rule: PASS->FAIL {flips(verdicts)[0]}, FAIL->PASS {flips(verdicts)[1]}")
        print(f"V13 latch (3 over / 3 under 80%): PASS->FAIL {flips(latched_v)[0]}, FAIL->PASS {flips(latched_v)[1]}")
    report("after ramp")
elif mode == "ramp":
    report("start")
    glitch_seen, steps = 0, 100
    for i in range(1, steps+1):
        m.mav.param_set_send(m.target_system, m.target_component, b"SIM_GPS1_GLTCH_X", i*0.00001, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        pump(1.0)
        e = last.get("EKF_STATUS_REPORT")
        if e and e.flags & 32768: glitch_seen += 1
        if i % 25 == 0: report(f"step {i} (offset {i*0.00001:.5f} deg)")
    print("ekf glitch flag seen at", glitch_seen, "of", steps, "steps")
    pump(5); report("after ramp +5 s")
else:
    report(mode)
