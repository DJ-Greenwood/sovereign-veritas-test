"""tools/consumer.py from the command line: act once, never go backwards (docs/ATTACK_HARNESS.md round 3)."""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "runs", "vehicle_sitl_v13", "sv_package_a911244dfcf7.json")
OLD = os.path.join(ROOT, "runs", "vehicle_sitl_v12", "sv_package_1506bcc87b3f.json")


def digest(p):
    return json.load(open(p))["package_sha256"]


def run(pkg, log, state):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "consumer.py"), "accept", pkg,
                           "--witness-log", log, "--state", state], capture_output=True, text=True)


def write_log(path, pkgs):
    with open(path, "w") as fh:
        fh.write("# sv witness log v0\n" + "".join(f"{i} {digest(p)}\n" for i, p in enumerate(pkgs, 1)))


def test_accept_once_then_refuse_replay(tmp_path):
    log, st = tmp_path / "w.log", tmp_path / "s.json"
    write_log(log, [OLD, PKG])
    assert run(PKG, str(log), str(st)).returncode == 0
    r = run(PKG, str(log), str(st))
    assert r.returncode == 1 and "replay" in r.stdout


def test_rollback_after_seeing_more_is_refused(tmp_path):
    full, rolled, st = tmp_path / "full.log", tmp_path / "rolled.log", tmp_path / "s.json"
    write_log(full, [OLD, PKG])
    write_log(rolled, [OLD])
    assert run(PKG, str(full), str(st)).returncode == 0
    r = run(OLD, str(rolled), str(st))
    assert r.returncode == 1 and "rollback" in r.stdout
    before = open(st).read()
    assert run(OLD, str(rolled), str(st)).returncode == 1 and open(st).read() == before  # state unchanged


def test_unreadable_log_could_not_look(tmp_path):
    log = tmp_path / "w.log"
    log.write_text("not a witness log\n")
    assert run(PKG, str(log), str(tmp_path / "s.json")).returncode == 2
