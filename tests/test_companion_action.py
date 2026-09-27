"""docs/COMPANION_ACTION.md, CA1-CA5: the Gate on veritas-companion delegation records."""
import copy, importlib.util, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ca = _load("companion_action_t", "tools/companion_action.py")
vp = _load("verify_package_ca", "tools/verify_package.py")

DET = {"status": "SUPPORTED", "delegated_to": "deterministic", "final_result": "40", "task_id": "a"}


def make(rec, tmp_path):
    return ca.package_for(rec, "t:1", "normal", str(tmp_path))


def failed(pkg):
    return [n for n, ok, _ in vp.verify(pkg) if not ok]


def reseal(pkg):
    prev = None
    for entry in pkg["provenance"]["chain"]:
        entry["record"]["previous_digest"] = prev
        entry["record_digest"] = prev = vp.sha(vp.canon(entry["record"]))
    pkg["package_sha256"] = vp.sha(vp.canon({k: v for k, v in pkg.items() if k != "package_sha256"}))
    return pkg


def test_ca1_tool_answer_is_allowed_and_released(tmp_path):
    pkg = make(DET, tmp_path)
    assert pkg["decision"] == {"decision": "ALLOW", "reasons": []}
    assert pkg["measurement"]["released_sha256"] == vp.sha("40")
    assert failed(pkg) == []


def test_ca2_conflict_and_escalation_defer(tmp_path):
    for st in ("UNCERTAIN", "ESCALATE"):
        pkg = make({"status": st, "delegated_to": "large_model", "final_result": "x"}, tmp_path)
        assert pkg["decision"] == {"decision": "DEFER", "reasons": ["verification_insufficient_evidence"]}
        assert pkg["measurement"]["released_sha256"] is None and failed(pkg) == []


def test_ca3_cached_needs_a_deterministic_origin(tmp_path):
    base = {"status": "CACHED", "delegated_to": "cache", "final_result": "40"}
    got = {o: make(dict(base, **({"cached_origin": o} if o else {})), tmp_path)["decision"]["decision"]
           for o in ("deterministic", "large_model", None)}
    assert got == {"deterministic": "ALLOW", "large_model": "DEFER", None: "DEFER"}


def test_ca4_unknown_status_refuses(tmp_path):
    for rec in (dict(DET, status="WHATEVER"), {"unparsed_line": "not json"}):
        pkg = make(rec, tmp_path)
        assert pkg["decision"]["decision"] == "REFUSE" and failed(pkg) == []


def test_ca5_relabelled_status_is_refused(tmp_path):
    pkg = make({"status": "UNCERTAIN", "delegated_to": "large_model", "final_result": "x"}, tmp_path)
    forged = copy.deepcopy(pkg)
    art = vp.json.loads(vp.base64.b64decode(forged["artifact"]["bytes_b64"]))
    art["record"]["status"] = "SUPPORTED"
    art["record"]["delegated_to"] = "deterministic"
    raw = vp.canon(art).encode()
    forged["artifact"]["bytes_b64"] = vp.base64.b64encode(raw).decode()
    assert "artifact_digest" in failed(forged)          # no reseal
    forged["artifact"]["sha256"] = vp.sha(raw)
    reseal(forged)
    assert "measurement_recomputed" in failed(forged)   # digests redone, old check kept


def test_bound_action_value_must_be_the_record_answer(tmp_path):
    pkg = make(DET, tmp_path)
    pkg["provenance"]["chain"][-1]["record"]["action"]["parameters"] = {"value": "41"}
    assert failed(reseal(pkg)) == ["companion_check_bound"]


def test_bound_released_hash_must_match(tmp_path):
    pkg = make(DET, tmp_path)
    pkg["measurement"]["released_sha256"] = vp.sha("41")
    assert failed(reseal(pkg)) == ["companion_check_bound"]
