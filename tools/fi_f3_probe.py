"""FIX-1 / FIX-5 / FIX-6 probe for F3 (docs/FI_FIX_PREREG.md). Uses the real harness fixtures.

FIX-1: U9 now gives (0, 0, raised ValueError, None); U0 and every other registered cell unchanged vs the pinned run.
FIX-6: with F3 bypassed (--sabotage) U9 must again show an effect, and the probe must exit 1.
Exit 0 only on the RECORDED outcome.
"""
import os, sys, tempfile, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fault_injection as fi
import sovereign_veritas.workflow as wf

RECORDED = ((True, True), "79fbe9b81d4ebe9e4048a7c8bd7d3380851dac9930c5d83fefacbf93941c3ac5")


def main(argv):
    sab = "--sabotage" in argv
    if sab:  # bypass F3: make math.isfinite always true inside the workflow module
        class _M:
            @staticmethod
            def isfinite(x):
                return True
        wf.math = _M
    cells = {}
    with tempfile.TemporaryDirectory() as tmp:
        for c in fi.WORKFLOW_EXPECT:
            obs, _, _ = fi.run_cell(c, tmp)
            cells[c] = (obs["effects"], obs["records"], obs["outcome"], obs["recorded"])
    u9_ok = cells["U9"] == (0, 0, "raised ValueError", None)
    others_ok = {c: cells[c] == fi.WORKFLOW_EXPECT[c] for c in cells if c not in ("U9", "U0")}
    # U0's registered tuple was wrong (ALLOW vs ALLOW/SUCCEEDED; FI-1 refuted, kept): compare to the observed pinned value
    others_ok["U0"] = cells["U0"] == (1, 1, "ok", "ALLOW/SUCCEEDED")
    for c, v in cells.items():
        print(("FIXED" if c == "U9" and u9_ok else "SAME " if others_ok.get(c) else "DIFF ") + f" {c} {v}")
    print("FIX-1", "HELD" if u9_ok else "REFUTED", "(U9)")
    print("regression on other cells:", "none" if all(others_ok.values()) else [c for c, v in others_ok.items() if not v])
    held = (u9_ok, all(others_ok.values()))
    digest = hashlib.sha256(json.dumps(cells, sort_keys=True).encode()).hexdigest()
    print("VERDICT", sum(held), "of 2 as registered")
    print("DIGEST", digest)
    if RECORDED is None:
        print("RECORDED not pinned yet")
        return 1
    return 0 if (tuple(held), digest) == RECORDED else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
