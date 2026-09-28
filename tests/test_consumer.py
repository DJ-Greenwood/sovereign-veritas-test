#!/usr/bin/env python3
"""tools/consumer.py: first-use then refuse replay (G1-3)."""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "runs" / "vehicle_sitl_v12" / "sv_package_1506bcc87b3f.json"
PKG = ROOT / "runs" / "vehicle_sitl_v13" / "sv_package_a911244dfcf7.json"
THIRD = ROOT / "runs" / "vehicle_sitl" / "sv_package_aa2fd72afe52.json"
CONSUMER = ROOT / "tools" / "consumer.py"


def digest(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))["package_sha256"]


def run(pkg, log, state):
    return subprocess.run(
        [sys.executable, str(CONSUMER), "accept", str(pkg),
         "--witness-log", str(log), "--state", str(state)],
        capture_output=True, text=True,
    )


def write_log(path, pkgs):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# sv witness log v0\n" + "".join(f"{i} {digest(p)}\n" for i, p in enumerate(pkgs, 1)))


def test_accept_once_then_refuse_replay(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG])
    r1 = run(PKG, log, st)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert "CONSUMER  ACCEPTED" in r1.stdout
    r2 = run(PKG, log, st)
    assert r2.returncode == 1, r2.stdout + r2.stderr
    assert "already accepted" in r2.stdout or "REFUSED" in r2.stdout


def test_rollback_after_seeing_more_is_refused(tmp_path):
    log, st = tmp_path / "full.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG, THIRD])
    assert run(THIRD, log, st).returncode == 0
    short = tmp_path / "short.log"
    write_log(short, [OLD, PKG])
    r = run(PKG, short, st)
    assert r.returncode == 1, r.stdout
    assert "rollback" in r.stdout.lower() or "REFUSED" in r.stdout


def test_garbage_log_is_unreadable(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    log.write_text("not a witness log\n", encoding="utf-8")
    r = run(PKG, log, st)
    assert r.returncode == 2
    assert "COULD NOT LOOK" in r.stdout or "WitnessUnreadable" in r.stdout
