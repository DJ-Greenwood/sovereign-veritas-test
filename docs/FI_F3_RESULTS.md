# FI-FIX F3 results — reject non-finite prediction uncertainty

Status: Draft, verified reference code. Registration: docs/FI_FIX_PREREG.md (a36e3dc), committed before any fix code. Claude-assisted (Claude Sonnet 5.5); Chad reviewed results and CI, not the code line by line.

## Failures and caveats first
- **Only F3 was built.** F1, F2, F4 (the I-B, I-C and restart findings) are untouched: E3, E4 still show an effect with no record, E2 still records FAILED after an effect, E4r still executes twice. Run output: `invariant violations: {"I-A": [], "I-B": ["E3", "E4"], "I-C": ["E2"]}`.
- **FI-1 stays refuted.** The U0 tuple registered in FI_PREREG.md was wrong about the code (`ALLOW` vs `ALLOW/SUCCEEDED`). Not edited.
- **The registration said "harness FI-2 written after this commit".** I reused tools/fault_injection.py (re-pinned, old pin kept as RECORDED_PRE_F3) plus a small probe, tools/fi_f3_probe.py, instead of a separate harness version. Deviation, disclosed.
- **FIX-1 ran in the same session that wrote it, by the same author.** Not independent.

## Change
sovereign_veritas/workflow.py: after `predictor.predict`, a prediction whose `uncertainty` is a non-bool int/float and not finite raises `ValueError` before the adversary, verifier, gate or executor. Other types pass unchanged (not validated: string or None uncertainty is not rejected).

## Results
- **FIX-1 HELD.** U9 now `(0, 0, 'raised ValueError', None)`; no other cell changed (probe: "regression on other cells: none").
- **FIX-5 HELD for F3.** `450 passed, 1 skipped`, same as before.
- **FIX-6 HELD.** With the check bypassed the probe shows U9 acting again and exits 1.
- **Side effect on the earlier harness:** FI-2 and FI-8 now hold as originally registered (8 of 9; FI-1 still refuted). Digest c77d529f…2057.
- Probe digest 79fbe9b81d4ebe9e4048a7c8bd7d3380851dac9930c5d83fefacbf93941c3ac5.

## Not shown
Whether NaN reached the ledger as non-standard JSON before the fix (not traced). Nothing run on the S25. Other non-finite sources (e.g. NaN in `prediction.value`) are not checked.

## Door
FIX-2/3/4/7 (F1, F2, F4) remain unrun.
