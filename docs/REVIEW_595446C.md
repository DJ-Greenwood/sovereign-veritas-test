# Adversarial review of `595446c`: what crashed, what was fixed, what is left

**Date:** 2026-09-30. **Scope:** `tools/verify_package.py` and the action layer, as registered in an
adversarial verifier-review prompt supplied by Chad Holland. **Done by:** Claude (Anthropic). Container
x86_64 only. **S25: NOT VALIDATED.**

## Failures first

No input found in this review was **accepted** by the verifier. Five input classes **crashed** it with an
uncaught traceback and exit 1, which is the same exit code as "checks failed". A caller could not tell
malformed input from a tampered package. All five fail on `595446c` and are fixed here.

| # | input | where it broke | before | after |
|---|---|---|---|---|
| F1 | top level is `[]`, `null`, `1` or `"x"` | `main()` → `verify()` calls `.get` | AttributeError, exit 1 | COULD NOT LOOK, exit 2 |
| F2 | `provenance.chain` is a string | `unknown_nested_keys` iterates characters | AttributeError, exit 1 | COULD NOT LOOK, exit 2 |
| F3 | JSON nested ~100,000 deep (bare, or inside a valid package) | `json.loads` | RecursionError, exit 1 | COULD NOT LOOK, exit 2 |
| F4 | `verifier.validation.min_coverage` = ±10**400 | `validation_status`: `math.isfinite` before the range test (added in `595446c`, by me) | OverflowError, exit 1 | MALFORMED → check fails, exit 1, no traceback |
| F5 | vehicle `alt_m`, `battery_pct`, `gps_sats`, `gps_fix_type` or `lat_e7` = 10**400, digests recomputed | `is_finite_number` → `math.isfinite` | OverflowError, exit 1 | not finite → check fails, exit 1, no traceback |

F4 and F5 exit 1, not 2, on purpose. The package parses, and a field is out of range. That is the same
outcome as NaN or ±Infinity in the same field (`tests/test_nonfinite_verifier.py`): the verifier looked
and the check failed. An earlier draft of this review said F4 should exit 2. That was wrong for
consistency with the existing tests.

F5 was not found by `tools/nonfinite_probe.py`. That probe reseals the chain and the package digest, but
it does not recompute `artifact_sha256`, `input_digest` or `output_sha256`. So a changed request or
snapshot fails earlier, on a digest, and `vehicle_check` is never reached. F5 was found by a static read
of the `alt_m` path, then forged the way `tools/attack_harness.py` does.

## Changes

- `tools/verify_package.py`:
  - `main()` refuses a non-object top level.
  - `main()` adds `AttributeError` and `RecursionError` to the COULD NOT LOOK tuple.
  - `validation_status` tests the range before `isfinite`. NaN fails the range test by itself.
  - `is_finite_number` returns False on `OverflowError`, which its own docstring already required.
- `tests/test_malformed_input.py`: 15 cases. 12 fail on `595446c`. The 3 in-range `min_coverage` positives
  pass on both.
- `tools/nonfinite_probe.py`: adds ±10**400 (judged against the finite change) and True/False (judged
  against the int of the same value, so an in-range `True` is not a false finding). `--selftest` now also
  re-plants the `595446c` `min_coverage` rule and must find its crash.

## Checked, no change

- **Action layer, `int(params["alt_m"] * 1000)`** (`tools/vehicle_action.py`, lines 197 and 199):
  - `--alt` is `argparse type=float`, so `1e400` becomes `inf`, never a huge int.
  - `vehicle_check` refuses a non-finite or out-of-range altitude before the Gate can ALLOW.
  - Execution requires ALLOW, so the conversion is not reachable with NaN, Infinity or a huge int.
  - The agent-side copy of `is_finite_number` has the same `OverflowError` pattern as F5, but its inputs
    are argparse floats and MAVLink ints. Unreachable from the CLI; recorded below, not changed.
- **A10 (witness rollback).** Already registered in advance as P11 ("the gap, stated in advance") in
  [ATTACK_HARNESS.md](ATTACK_HARNESS.md), with the consumer-side mitigation as P14. Left alone.
- **Duplicate JSON keys.** Last one wins. With a single verifier, the signed bytes and the parsed values
  cannot diverge. Only a second implementation could read them differently (see below).

## Follow-up (not investigated, on purpose)

1. **H1** `zone_status` accepts `true` as a thermal reading of 1. Any in-range int would pass the same way.
   These readings are already listed as editable in an unsigned package by `tools/field_sweep.py`.
2. **H2** Reject duplicate JSON keys (`object_pairs_hook`) before an independent implementation exists
   (issue #4 B10). Otherwise two verifiers can read the same signed bytes differently.
3. **H3** No bound on file size, chain length, witness-log size or signature size.
4. Canonical-form differentials across implementations (−0 vs 0, 1 vs 1.0, escapes, `ensure_ascii=False`).
5. `nonfinite_probe.py` does not recompute the artifact, input and output digests, so fields behind them
   (F5's class) are out of its reach. Covered here by one regression test, not by the probe.
6. The agent-side `is_finite_number` in `tools/vehicle_action.py` (see above).
7. Replay and `--allow-recorded-only`, and per-invariant mutant coverage, from the review prompt.

## Results (container, x86_64, pasted)

```
pytest tests/test_malformed_input.py           15 passed          (on 595446c: 12 failed, 3 passed)
pytest (full suite)                            428 passed
python tools/nonfinite_probe.py --selftest     self-test: planted rule -> 5 FAIL-OPEN found (PASS)
                                               self-test: planted 595446c rule -> 3 CRASH found (PASS)
python tools/nonfinite_probe.py                VERDICT  no fail-open, no crash over 8 package(s)
  (7 vehicle/model/companion packages)         VERDICT  no fail-open, no crash over 7 package(s)
python tools/verifier_mutants.py               VERDICT  27 of 27 KILLED, 0 SURVIVED  (472 s)
python tools/attack_harness.py --round2        P0 P1 P2 P3 P4 P5 P6 P7 P9 P10 P11  HELD (all, after these changes)
```
