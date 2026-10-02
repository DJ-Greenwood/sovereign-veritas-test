# XB-1 — Execution boundary: does a ledger duplicate check stop a duplicate external effect?

**Status: REGISTERED, UNRUN.** Committed before `tools/execution_boundary_probe.py` exists.
Registered 2026-10-02 by Claude (Opus 5.5) at Chad Holland's request.

## Origin (external observation, kept at its stated strength)

Davorin Popović reported that a Codex-assisted review of commit `386716a` found
`EvidenceWorkflow.run()` calls `executor.execute(action)` **before** `evidence_sink.record(evidence)`,
and that a local probe with a counting executor saw the executor invoked twice for a repeated
`record_id`, the ledger rejecting the duplicate only afterwards. He stated he had **not**
independently reproduced the probe. Until this experiment runs, that is a reported observation.

Reading of the code (not evidence): `sovereign_veritas/workflow.py` is unchanged between
`386716a` and `794a86b` (last change `9308ce3`, an ancestor of both). Duplicate rejection lives in
`Ledger.append` / `FileLedger.append`, i.e. inside `record()`, i.e. after `execute()`.

## The distinction under test

`LEDGER DUPLICATE PROTECTION` vs `EXTERNAL SIDE-EFFECT DUPLICATE PROTECTION`.
`RECORD_REJECTED ≠ EXTERNAL_EFFECT_REVERSED`.

The object counted is the **external effect** (a counting executor), not ledger rows.

## Cases and predictions — current code (`386716a` and `794a86b`)

| ID | Case | Predicted effects | Predicted records | Other |
|----|------|------|------|------|
| X0 | anti-vacuity: two runs, **distinct** record_ids, ALLOW | 2 | 2 | no error |
| X0r | anti-vacuity: REFUSE (capability not granted) | 0 | 1 | |
| X1 | same record_id twice, in-memory `LedgerSink` | **2** | 1 | 2nd run raises `duplicate record_id` |
| X2 | same, durable `FileLedger` | **2** | 1 | 2nd raises |
| X3 | same, `FileLedger` reloaded in a new workflow instance (process-restart analogue) | **2** | 1 | 2nd raises |
| X4 | two threads, same record_id, slow executor (50 ms) | **2** | 1 | one thread raises |
| X5 | executor succeeds, sink fails on write | **1** | **0** | effect with no record; exception propagates |
| X6 | executor raises | 0 | 1 (`execution_status = FAILED`) | exception re-raised |

Registered expectation: X1–X3 **reproduce Davorin's report** at both commits.
If X1 shows 1 effect, the report is NOT reproduced and that is the finding.

## Candidate minimal mechanism (registered before it is written)

"Refuse before effect": if the sink can answer whether `record_id` already exists, check it before
`execute()` and raise without executing. Predicted under that change:

| ID | Predicted effects | Note |
|----|------|------|
| X0, X0r, X6 | unchanged | anti-vacuity: the fix must not stop legitimate work |
| X1, X2, X3 | **1** | fixed |
| X4 | **2** | NOT fixed: check-then-act race; needs an atomic reservation |
| X5 | 1 effect, 0 records | NOT fixed: needs write-ahead intent, a ledger-format decision |

So the smallest mechanism is predicted to close the sequential class only. Anything stronger
(atomic reservation, intent-before-execute) changes the ledger format and is **Chad's decision**,
not this experiment's.

## Not tested (doors)

- **Authority revalidation at execution (Davorin / Sougata, T1 → T2).** `run()` evaluates the Gate and
  executes in the same call with no deferred-execution API, so a stale authorization cannot be
  replayed through it. The window exists only between `gate.evaluate` and `execute` in one call.
  Unrun: an execution gateway that accepts a stored ALLOW later.
- **Retry with uncertain outcome.** Requires an executor that can report UNKNOWN. Unrun.
- Nothing here is measured on the S25.
