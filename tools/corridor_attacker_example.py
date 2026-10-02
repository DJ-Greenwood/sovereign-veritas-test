#!/usr/bin/env python3
"""corridor_attacker_example.py - reference attacker A4 (threshold ride) speaking the V14 JSON-lines protocol.

A starting point for the corroboration-corridor challenge (CHALLENGE.md). Run it through the harness:
  python tools/corridor_challenge.py --attacker "python tools/corridor_attacker_example.py"
It must print NO BREAK with a max breach of 30.9500 m, the same as the in-process A4.
"""
import json, sys

start, m, pushing, c = None, 0.0, False, None
for line in sys.stdin:
    msg = json.loads(line)
    if "hello" in msg:
        c = msg["constants"]
        print(json.dumps({"ok": True}), flush=True)
        continue
    if "bye" in msg:
        break
    o = msg["obs"]
    if start is None and o["allowed"]:
        start = o["t"]
    if start is not None:
        sp = o["setpoint_prev"]
        if not pushing and sp is not None and abs(sp[0] - c["target"][0]) < 1e-9 and abs(sp[1] - c["target"][1]) < 1e-9:
            pushing = True
        m = m + c["S"] if pushing else min(0.5 + (o["t"] - start), c["L"] + c["E"] - 0.05)
    g = [-m, 0.0]                                   # inward: pushes the true position outward
    e = [-min(m, c["E"]), 0.0]                      # aligned with g: the gap is |g| - E
    print(json.dumps({"g": g, "e": e}), flush=True)
