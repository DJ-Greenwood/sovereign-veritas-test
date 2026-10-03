# FI-FIX registration — closing the three findings from PR #23 (nothing built or run)

Status: Speculative (registration only). Written 2026-10-03, Claude-assisted (Claude Sonnet 5.5); not yet reviewed by Chad line by line.
Predecessor: docs/FI_RESULTS.md. Harness: tools/fault_injection.py (pinned RECORDED, not to be edited except by a new, labelled version).

## Why this is a registration and not a patch
Each fix changes recorded semantics (what the ledger contains, what the gate admits). That affects package verification and the
ledger format, so it needs Chad's decision before any code change. Nothing below is implemented.

## Candidate changes (each independent)
- **F1 write-ahead intent (targets I-B in E3/E4, E4r).** Before `executor.execute`, record `ALLOW` with `execution_status="INTENDED"`; after execution, record the outcome as a second record. If the intent write fails, no effect.
- **F2 outcome-truth (targets I-C in E2).** Add a status `FAILED_UNKNOWN_EFFECT` when the executor raises, so the record no longer asserts "no effect".
- **F3 non-finite rejection (targets U9).** The workflow rejects a prediction whose `uncertainty` is NaN or infinite, before the gate (fail closed).
- **F4 duplicate record id (targets E4r).** A second run with an existing `record_id` and an INTENDED or SUCCEEDED record refuses with no effect.

## Predictions (to be scored by a harness version FI-2, written after this commit and before any fix code)
- **FIX-1** With F3: U9 gives `(0, 0, raised ValueError, none)` and U0 is unchanged.
- **FIX-2** With F1: E3 and E4 give 0 effects (intent write fails or is refused), and I-B has no violations.
- **FIX-3** With F1 and F4: E4r gives effects 1, records 2 or fewer (restart does not re-execute).
- **FIX-4** With F2: E2 has no I-C violation; E1 (executor fails before any effect) is recorded as FAILED, not as unknown.
- **FIX-5** Regression: the existing 450 tests pass unchanged. Registered at confidence 0.4: F1 adds a record per ALLOW and will likely break tests that count records or read the last record's status. If it does, that is a result and the fix is not shipped.
- **FIX-6** Anti-vacuity: the sabotage mode (fix bypassed) must reproduce the current violations and exit 1.
- **FIX-7** Cost: F1 doubles ledger writes per ALLOW. Measured, not predicted as free.

## Rival (M14)
Simplest rival: document the gaps and change nothing. The fixes must beat "documented, known limitation" on a stated criterion: removing a violation without breaking the package verifier.

## Not covered (door, M15)
Real crash and disk-full on the S25; concurrent writers; idempotency keys enforced by the executor itself (outside this kernel's control).
