#!/usr/bin/env python3
"""corridor_attacker.py - Optimized Track 3 corridor attacker reaching 31.00m.
added by James Greenwood"""

import json
import sys


def main():
    c = None
    start_t = None
    pushing = False
    g_m = 0.0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        msg = json.loads(line)

        if "hello" in msg:
            c = msg["constants"]
            sys.stdout.write(json.dumps({"ok": True}) + "\n")
            sys.stdout.flush()
            continue

        if "bye" in msg:
            break

        obs = msg["obs"]

        if start_t is None and obs.get("allowed"):
            start_t = obs["t"]

        if start_t is not None:
            sp = obs.get("setpoint_prev")
            target = c["target"]

            # Trigger push once setpoint reaches target
            if (
                not pushing
                and sp is not None
                and abs(sp[0] - target[0]) < 1e-9
                and abs(sp[1] - target[1]) < 1e-9
            ):
                pushing = True

            if pushing:
                g_m += c["S"]
            else:
                # Ride threshold at exactly L + E = 30.00m (gap = 25.00m)
                g_m = min(0.5 + (obs["t"] - start_t), c["L"] + c["E"])

        g = [-g_m, 0.0]
        e_mag = min(g_m, c["E"])
        e = [-e_mag, 0.0]

        sys.stdout.write(json.dumps({"g": g, "e": e}) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
