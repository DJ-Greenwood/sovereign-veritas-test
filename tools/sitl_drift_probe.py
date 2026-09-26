#!/usr/bin/env python3
"""sitl_drift_probe.py - ArduPilot SITL only: ramp a slow GPS position offset (SIM_GPS1_GLTCH_X) and
report the TRUE position (SIMSTATE, which a real vehicle does not have) against the believed one.
Used for V11 in docs/VEHICLE_ACTION.md. Fence centre hard-coded to the default 35.3632, -96.9270.

  python tools/sitl_drift_probe.py ramp        # 100 steps of 0.00001 deg, one per second
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
if mode == "ramp":
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
