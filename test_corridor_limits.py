#!/usr/bin/env python3
"""test_corridor_limits.py - Edge case probe for corridor_challenge.py harness."""

import subprocess
import sys


def run_challenge_with_attacker(attacker_code):
    cmd = [
        sys.executable,
        "tools/corridor_challenge.py",
        "--attacker",
        f'{sys.executable} -c "{attacker_code}"',
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout


def main():
    print("=" * 70)
    print("CORRIDOR HARNESS EDGE-CASE PROBES")
    print("=" * 70)

    # Edge Case 1: Attacker exceeds maximum GNSS slew (S > 1.0m per tick)
    code_slew = (
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "  msg = json.loads(line)\n"
        "  if 'hello' in msg: print(json.dumps({'ok': True}), flush=True)\n"
        "  elif 'obs' in msg:\n"
        "    print(json.dumps({'g': [-10.0, 0.0], 'e': [0.0, 0.0]}), flush=True)\n"
    )

    rc1, out1 = run_challenge_with_attacker(code_slew)
    print("\n1. Excessive GNSS Slew (10.0m/tick > S=1.0m):")
    print(f"   Exit Code: {rc1} (Expected 3 for OUT OF MODEL)")
    print(f"   Verdict  : {next((l for l in out1.splitlines() if 'VERDICT' in l), out1.strip())}")

    # Edge Case 2: Attacker exceeds error bound (E > 5.0m)
    code_error = (
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "  msg = json.loads(line)\n"
        "  if 'hello' in msg: print(json.dumps({'ok': True}), flush=True)\n"
        "  elif 'obs' in msg:\n"
        "    print(json.dumps({'g': [0.0, 0.0], 'e': [-10.0, 0.0]}), flush=True)\n"
    )

    rc2, out2 = run_challenge_with_attacker(code_error)
    print("\n2. Excessive Error Bound (-10.0m > E=5.0m):")
    print(f"   Exit Code: {rc2} (Expected 3 for OUT OF MODEL)")
    print(f"   Verdict  : {next((l for l in out2.splitlines() if 'VERDICT' in l), out2.strip())}")

    # Edge Case 3: Attacker outputs NaN
    code_nan = (
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "  msg = json.loads(line)\n"
        "  if 'hello' in msg: print(json.dumps({'ok': True}), flush=True)\n"
        "  elif 'obs' in msg:\n"
        "    print(json.dumps({'g': [float('nan'), 0.0], 'e': [0.0, 0.0]}), flush=True)\n"
    )

    rc3, out3 = run_challenge_with_attacker(code_nan)
    print("\n3. NaN Output:")
    print(f"   Exit Code: {rc3} (Expected 3 for OUT OF MODEL)")
    print(f"   Verdict  : {next((l for l in out3.splitlines() if 'VERDICT' in l), out3.strip())}")


if __name__ == "__main__":
    main()