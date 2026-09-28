# Response to issue #5 (Nick Kouns) — registration and results

Status: **Closed** (2026-09-28). Findings accepted; both defects fixed on `main` at `2902a2c`.
Issue: https://github.com/holland202/sovereign-veritas/issues/5

Reviewer: **Nicholas Kouns** (@nicholaskouns-create). Reproduction and write-up against
holland202/sovereign-veritas @ `8f098e8`. Interactive reconstruction of the break and the
revision: https://spring-palm-cedar-willow.grok.me/ ("Threefold").

Credit is by name in STATUS.md, as CHALLENGE.md requires for a careful reproduction that
exposed unpublished implementation defects.

## Findings (accepted)

Neither finding needed the signing key. Against `keys/allowed_signers` / identity `holland202`,
a forged signature was still refused. A finite bad battery still FAILed. The published limits
(K1–K3, A3–A5, A7, A10) do not cover these cases.

### 1. `vehicle_check` fail-opened on NaN and Infinity

A v13 SITL takeoff package with only three readings changed:

- `battery_pct = NaN`
- `gps_fix_type = Infinity`
- `gps_sats = NaN`

The published checker returned `PASS` / `all takeoff rules hold`. Gate replay printed
`ALLOW []`. `verify_package.py` printed `VERDICT  CONSISTENT` (unsigned). A battery of 10 on
the same package still FAILed (`battery 10 % < 30 %`).

Cause: raw `<` / `>` comparisons. In IEEE arithmetic, `NaN < 30` and `Infinity < 3` are both
false, so the limit tests never fired. The gate then treated that PASS as permission.

Evidence retained under `evidence/attacks/issue-005/` (pre-fix baselines, poisoned packages,
post-fix verifier transcripts).

### 2. `consumer.py` accepted a non-canonical witness prefix

After anchoring the exact entry lines `1 <digest>`, the consumer accepted a log whose first
entry was `0001\t<digest>` (leading zeros, tab, trailing spaces, blank line under the header).
`str.split()` and `int("0001")` made the *parsed* prefix match while the byte string did not.
Two separate reads of the log path (freshness then consumer) left a TOCTOU window.

## Fixes (commit `2902a2c`)

- **Checker:** `tools/vehicle_action.py` and `tools/verify_package.py` require a finite int or
  float before any comparison. Non-finite readings produce explicit FAIL reasons
  (`… is non-finite or non-numeric`). Producer and independent verifier agree
  (`test_nonfinite_verifier_matches_producer`).
- **Witness:** `read_witness_log` reads raw bytes, demands exact LF-terminated canonical lines,
  rejects tabs, leading zeros, trailing spaces, blank lines, and CR. Seq text must be the exact
  decimal of the next index. `consumer.py` takes one already-read snapshot (no double-read).
- Tests: `test_nonfinite_*`, `test_w8_noncanonical_witness_entry_is_rejected`.

Post-fix: the same poisoned package recomputes to REFUSE / `verification_not_passed`; non-canonical
witness entries raise `WitnessUnreadable`.

## What held

- Ed25519 over the published allowed_signers line (wrong key, empty signature, truncation, bit flips).
- Finite limit checks (battery 10 still fails).
- The signature mechanism itself; the hole was what a signature would have sealed.

## Out of scope for this issue (already on the sv.gate/1 list)

DEFAULTED runtime treated as healthy on ALLOW remains a stated limitation of sv.gate/0 and is
scoped as G1-6 in `docs/SV_GATE_1_SCOPE.md`. It is not a defect under the current contract.

## Credit

Nicholas Kouns (@nicholaskouns-create) — issue #5, careful reproduction, and the public
Threefold reconstruction at https://spring-palm-cedar-willow.grok.me/
