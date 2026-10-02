# XB-2 — Where can "this effect happens once, under current authority" become a durable fact?

**Status: REGISTERED, UNRUN.** Committed before `tools/xb2_boundary_probe.py` exists.
Registered 2026-10-02 by Claude (Opus 5.5) at Chad Holland's request.

## Origin

XB-1 left two cases open: X4 (concurrent race) and X5 (effect, then the record write fails). After reading
the XB-1 results, Davorin Popović asked where the system should establish "the durable fact that this exact
external effect is permitted to occur once, under authority that is still current at the execution
boundary". That is his question; the designs, predictions and probe below are this project's.

## The claim being tested (stated so it can be wrong)

Known result from distributed systems, applied here: **no component on the authorizing side can, alone,
make an external effect happen exactly once.** If the process dies after the effect and before the record,
recovery must either retry (risk a duplicate: at-least-once) or not (risk a missing or unconfirmed effect:
at-most-once). Moving the logic into a gateway does not change that. Only (a) an effect the external system
de-duplicates by an idempotency key, or (b) a way to ask the external system what happened, closes it.

If XB-2 shows a design that reaches zero duplicates **and** a truthful definitive record at every crash point
**without** external cooperation, the claim is refuted.

## Designs (arms)

| Arm | What it is | Code |
|---|---|---|
| A1 | current workflow after PR #8: `has_record` pre-check, execute, record | **real** `EvidenceWorkflow` + `LedgerSink` |
| A2 | + atomic reservation: durable intent written (insert-if-absent, locked) before execute; recovery does not retry an intent with no outcome | reference model |
| A3 | A2 + execution gateway: authority re-checked immediately before execute | reference model |
| A4 | A3 + idempotency key sent with the effect; recovery and ambiguous outcomes ask the external system | reference model, **cooperative** external system |
| A4n | A4 against a **non-cooperative** external system (no de-duplication, cannot be asked) — anti-vacuity | reference model |

A2–A4n are a reference model written for this experiment, not code in the kernel. Their predictions follow
from their definitions; what the run adds is that each definition is executed against every case and the
A1 row is measured on the real workflow.

## Cases

| ID | Case |
|---|---|
| C0 | one ordinary authorized request (anti-vacuity: every arm must give 1 effect, record CONFIRMED) |
| C1 | same key twice, sequentially |
| C2 | same key, two threads |
| C3 | authority revoked between decision and execution |
| C4 | crash after reservation, before the effect; then recovery |
| C5 | crash after the effect, before the record; then recovery |
| C6 | effect happens, response lost (timeout); caller retries the same key |

Scored per arm × case: **external effects** (counted at the external system) and the **final record state**.
A record is **false** if it contradicts the world (e.g. FAILED or absent when the effect happened, or
CONFIRMED when it did not). UNCONFIRMED / UNKNOWN are honest but not definitive.

## Predictions (effects, final record)

| | A1 | A2 | A3 | A4 | A4n |
|---|---|---|---|---|---|
| C0 | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED |
| C1 | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED |
| C2 | **2**, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED | 1, CONFIRMED |
| C3 | N/A (decision and execution are one call; no deferred-execution API) | **1** (not re-checked), CONFIRMED | 0, REFUSED | 0, REFUSED | 0, REFUSED |
| C4 | 1, CONFIRMED (no intent survives, caller retries) | **0**, UNCONFIRMED | **0**, UNCONFIRMED | 1, CONFIRMED | **0**, UNCONFIRMED |
| C5 | **2**, CONFIRMED (retry duplicates) | 1, UNCONFIRMED | 1, UNCONFIRMED | 1, CONFIRMED | 1, UNCONFIRMED |
| C6 | 1, **FAILED (false)** | 1, UNKNOWN | 1, UNKNOWN | 1, CONFIRMED | 1, UNKNOWN |

Registered consequences:

- **P1.** Only A4 reaches the expected effect count **and** a definitive true record in all 7 cases.
- **P2 (anti-vacuity of P1).** A4n's row equals A3's row: the guarantee comes from the external system's
  cooperation, not from the gateway.
- **P3.** A3 differs from A2 **only** on C3. A gateway's re-check of authority is its sole measured gain.
- **P4 (new, about real code).** A1 C6: the real workflow records `execution_status = FAILED` for an
  executor that performed the effect and then timed out, and PR #8's pre-check then refuses the retry. The
  ledger states the effect did not happen while it did. XB-1 X6 tested only failure *before* the effect.
- **P5.** No arm records a false CONFIRMED.

## Doors (unrun)

- Lease expiry and fencing tokens for a reservation whose holder dies mid-effect (multi-process).
- Real external systems: which of Chad's executors (vehicle, model, companion) can accept an idempotency key
  or be queried afterwards — that decides whether A4 is available at all.
- Nothing here is measured on the S25.
