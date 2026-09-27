# Companion action: the gate decides whether a veritas-companion answer may be used (registered 2026-09-27, before it was built)

**What it connects.** veritas-companion (github.com/holland202/veritas-companion) answers questions
about a log with cheap deterministic tools first, and hands the rest to a large model. Each answer is
one line in its delegation log (JSONL). `tools/companion_action.py` turns one such line into an
evidence package. The gate decides whether a consumer may act on the answer (`use_answer`), and
`tools/verify_package.py` re-derives that decision from the package alone.

**The rule (measurement kind `companion_route_check`).** The check reads only the logged record:

| record | check | gate |
|---|---|---|
| `status` SUPPORTED, `delegated_to` deterministic | PASS | ALLOW |
| `status` CACHED, `cached_origin` deterministic | PASS | ALLOW |
| `status` UNCERTAIN (the tools saw conflicting values) | INSUFFICIENT_EVIDENCE | DEFER |
| `status` ESCALATE, or any answer from the large model, or CACHED from the large model or of unknown origin | INSUFFICIENT_EVIDENCE | DEFER |
| anything else (unknown status, missing fields) | FAIL | REFUSE |

A large-model answer is never ALLOWed here. Nothing in the record lets the check recompute whether
it is right. It is deferred to a human or a stronger check, not refused, because it may well be
right. (Before this work, a CACHED record did not say which tier had produced it. veritas-companion
`fff7f84` added `cached_origin`, so a model answer replayed from the cache cannot pass as a
tool answer.)

**The verifier.**
- It recomputes the check from the artifact (the record's canonical JSON).
- It requires the recorded verification to equal that check.
- It requires the action to be `use_answer` with parameter `value` equal to the record's
  `final_result`.
- A new guard, `companion_check_bound`, is added to `tools/verifier_mutants.py`'s list, like every
  other guard.

## Predictions

- **CA1 (anti-vacuity: it can ALLOW)** A SUPPORTED deterministic record gives ALLOW; the package
  verifies CONSISTENT.
- **CA2** UNCERTAIN and ESCALATE records give DEFER with reason `verification_insufficient_evidence`.
- **CA3** CACHED gives ALLOW only with `cached_origin` deterministic. With `large_model`, or with no
  `cached_origin` (a log written before `fff7f84`), it gives DEFER.
- **CA4** A record with an unknown status gives REFUSE.
- **CA5** Editing the recorded status (UNCERTAIN → SUPPORTED) without recomputing the digests is
  refused by the verifier. So is recomputing the digests while keeping the old check or decision.
- **CA6** `tools/verifier_mutants.py` reports `companion_check_bound` KILLED, and the null mutant
  still passes.
- **CA7 (end to end, on veritas-companion's C003 task)** The companion answers every C003 question on
  seeds 1-20 twice. The first pass fills the cache, and escalated questions go to the test-double
  model, whose output is NOT A RESULT. The second pass is served from the cache. Every logged record
  becomes a package. Then:
  - (a) every ALLOWed answer is correct against the task's truth, so there are 0 false ALLOWs;
  - (b) every UNCERTAIN or ESCALATE record, and every CACHED record from the large model, is
    DEFERred;
  - (c) every package verifies CONSISTENT.

**Unrun, left open (CA8).** A consumer that acts on DEFER by asking a second, independent tool, and
records that as a second package chained to the first.

**Limits.** The check trusts the companion's own label for which tier answered (`delegated_to`,
`cached_origin`). A compromised companion could lie about it. Only a signature by the companion's
key, not its log line, would bind the label to the companion. The gate judges the route an answer
took, not the answer.

## Results (x86_64, Python 3.11.15, 2026-09-27)

- **CA1-CA5 held** (`tests/test_companion_action.py`, 7 tests). A tool answer is ALLOWed and released.
  UNCERTAIN and ESCALATE are DEFERred. CACHED is ALLOWed only with origin `deterministic`; `large_model`
  and a missing origin DEFER. An unknown status and an unparseable line are REFUSEd. A status relabelled
  to SUPPORTED fails `artifact_digest` without a reseal, and `measurement_recomputed` with one.
- **CA6 held.** `python tools/verifier_mutants.py --only companion_check_bound`: KILLED by
  `test_bound_action_value_must_be_the_record_answer`. The null mutant passed.
- **CA7 held, 3 of 3** (veritas-companion `experiments/C005_gate_bridge/`, `4f…` onward):
  - 640 delegation records became 640 packages, all CONSISTENT.
  - 480 answers were ALLOWed, 0 of them wrong.
  - Every UNCERTAIN (60), ESCALATE (20) and cached large-model answer (80) was DEFERred.

As registered, a known limit remains: the check trusts the companion's own labels, so it judges the
route an answer took, not the answer.
