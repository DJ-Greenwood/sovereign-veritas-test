# Non-finite probe: the issue #5 class, searched for in every numeric field (2026-09-30)

Issue #5 (Nick Kouns) showed that `battery_pct = NaN` passed a takeoff check. That was one field in one
checker. `tools/nonfinite_probe.py` searches the whole package for the same class. For every numeric
field it reseals three variants (a large finite change; NaN; ±Infinity) and verifies each. A **FAIL-OPEN**
is a field where the finite change FAILS but a non-finite value verifies CONSISTENT. A **CRASH** is any
uncaught exception in the verifier.

## Found on the first run (all 8 packages in `evidence/`)

| field | value | before | after |
|---|---|---|---|
| `verifier.validation.failed_probes` | NaN, −Infinity | recomputed `VALIDATED`: package **CONSISTENT** | `MALFORMED`: check fails |
| `verifier.validation.min_coverage` | −Infinity | `VALIDATED`: **CONSISTENT** | `MALFORMED` |
| `measurement.rounds` | ±Infinity | verifier **crashed** (OverflowError) | refused: needs an int in 1..10,000,000 |
| `measurement.rounds` | 10¹² (finite) | verifier ran about 10¹² hashes, effectively forever (a denial of service; found while writing the regression test) | refused in under 1 s |

**Cause.** `failed_probes > 0` is false for NaN and for −Infinity, and `mp / total >= min_coverage` is true
for −Infinity. `range(int(rounds))` trusts a field the package's author writes.

**Fix** (`tools/verify_package.py`). Probe counts must be plain ints ≥ 0 and consistent
(passes ≤ probes ≤ total). Coverage must be a finite number in [0, 1]. Chain rounds must be an int in
1..10,000,000; `make_package` uses 200,000.

## After the fix

```
sv_package_118a02b75646.json: baseline exit 0, 196 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_1956abdc6154.json: baseline exit 0, 201 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_3a9dbf53aee6.json: baseline exit 0, 201 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_45c6ad182584.json: baseline exit 0, 197 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_5bfc70dfcfa2.json: baseline exit 0, 190 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_7548237bceca.json: baseline exit 0, 202 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_df46427defc7.json: baseline exit 0, 201 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
sv_package_ed144097dece.json: baseline exit 0, 201 numeric fields x 3 non-finite values: 0 FAIL-OPEN, 0 CRASH
VERDICT  no fail-open, no crash over 8 package(s)
```

- **Anti-vacuity:** `python tools/nonfinite_probe.py --selftest` re-plants the pre-fix rule, and the probe
  must find it. Output: `self-test: planted rule -> 3 FAIL-OPEN found (PASS)`.
- **Regression:** `tests/test_nonfinite_verifier.py`, 22 cases. They fail on the old verifier: NaN and
  −Infinity gave `VALIDATED`, Infinity raised OverflowError, and 10¹² was still running after 3 s.

## Limits

- The 8 stored packages are all measurement packages (`sha256_chain`). Vehicle, model and companion
  packages carry other numeric fields. The probe takes any package path, and those kinds are **NOT YET
  PROBED**.
- Reseal is the attacker who lacks the signing key. A signed package also needs the key; this probes
  the checks, not the signature.
- Container only (x86_64). On the S25: **NOT VALIDATED**.
