"""XB-1 regression (docs/EXECUTION_BOUNDARY_RESULTS.md): a repeated record_id must be refused before the
executor runs, not after. Effects are counted at the executor, which stands in for the external world."""
import pytest

from sovereign_veritas.capability import Capability
from sovereign_veritas.evidence import Ledger, LedgerSink
from sovereign_veritas.file_ledger import FileLedger
from sovereign_veritas.interfaces.contracts import ActionProposal, Prediction
from sovereign_veritas.runtime import RuntimeState
from sovereign_veritas.workflow import EvidenceWorkflow


class _Sensor:
    def observe(self):
        return "o"


class _Predictor:
    def predict(self, observation):
        return Prediction(value="p", uncertainty=0.1, model_id="m")


class _Verifier:
    def verify(self, observation, prediction):
        return {"status": "PASS"}


class _Counting:
    def __init__(self):
        self.effects = 0

    def execute(self, action):
        self.effects += 1
        return {"n": self.effects}


def _run(wf, rid):
    return wf.run(record_id=rid, input_digest="abc", capability=Capability("read_only", True, ("fresh",)),
                  runtime=RuntimeState(platform="android", python_version="3.14.6"),
                  action=ActionProposal(capability="read_only", requested="read", parameters={}),
                  metadata={"fresh": True})


def _wf(sink, ex):
    return EvidenceWorkflow(sensor=_Sensor(), predictor=_Predictor(), verifier=_Verifier(),
                            executor=ex, evidence_sink=sink)


def test_repeated_record_id_in_memory_gives_one_effect():
    ex = _Counting()
    wf = _wf(LedgerSink(Ledger()), ex)
    _run(wf, "dup")
    with pytest.raises(ValueError, match="refused before execution"):
        _run(wf, "dup")
    assert ex.effects == 1


def test_repeated_record_id_after_file_ledger_reload_gives_one_effect(tmp_path):
    ex, path = _Counting(), tmp_path / "l.jsonl"
    _run(_wf(LedgerSink(FileLedger(path)), ex), "dup")
    with pytest.raises(ValueError, match="refused before execution"):
        _run(_wf(LedgerSink(FileLedger(path)), ex), "dup")
    assert ex.effects == 1


def test_distinct_record_ids_still_execute():  # anti-vacuity: the check must not stop legitimate work
    ex, sink = _Counting(), LedgerSink(Ledger())
    wf = _wf(sink, ex)
    _run(wf, "a")
    _run(wf, "b")
    assert ex.effects == 2 and len(sink.ledger.all()) == 2


def test_sink_without_has_record_keeps_previous_behaviour():
    """Documented limit: a sink that cannot answer has_record gets no pre-check (backward compatible)."""
    class Plain:
        def __init__(self):
            self.ledger = Ledger()

        def record(self, r):
            return self.ledger.append(r)

    ex = _Counting()
    wf = _wf(Plain(), ex)
    _run(wf, "dup")
    with pytest.raises(ValueError, match="duplicate record_id"):
        _run(wf, "dup")
    assert ex.effects == 2
