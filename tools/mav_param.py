#!/usr/bin/env python3
"""mav_param.py - set one parameter on a MAVLink autopilot and print the value it reports back.

Used in docs/VEHICLE_ACTION.md to inject faults into ArduPilot SITL (SIM_GPS1_ENABLE,
SIM_GPS1_GLTCH_X, ...). Kept apart from tools/vehicle_action.py on purpose: the tool under test
never injects its own faults.

  python tools/mav_param.py NAME VALUE [--link tcp:127.0.0.1:5760]
Exit: 0 set and confirmed | 1 the autopilot reported another value | 2 could not run
"""
import argparse, sys, time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("value", type=float)
    ap.add_argument("--link", default="tcp:127.0.0.1:5760")
    a = ap.parse_args()
    try:
        from pymavlink import mavutil
        m = mavutil.mavlink_connection(a.link, source_system=251, autoreconnect=False)
        if m.wait_heartbeat(timeout=15) is None:
            raise OSError("no heartbeat")
    except Exception as exc:  # noqa: BLE001
        print(f"COULD NOT RUN: {exc}")
        sys.exit(2)
    m.mav.param_set_send(m.target_system, m.target_component, a.name.encode(), a.value,
                         mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
    end = time.time() + 10
    while time.time() < end:
        p = m.recv_match(type="PARAM_VALUE", blocking=True, timeout=1)
        pid = None if p is None else (p.param_id if isinstance(p.param_id, str) else p.param_id.decode())
        if pid == a.name:
            print(f"{a.name} = {p.param_value:g}")
            sys.exit(0 if abs(p.param_value - a.value) < 1e-6 else 1)
    print(f"COULD NOT RUN: no PARAM_VALUE for {a.name}")
    sys.exit(2)


if __name__ == "__main__":
    main()
