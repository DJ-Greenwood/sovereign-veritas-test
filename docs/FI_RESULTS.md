# FI results — end-to-end failure injection (registration 6daa1fc)

Status: Draft, verified reference code. Harness: `tools/fault_injection.py`. Registration and expected tuples were not edited after the run.

## Failures lead (M8): 3 of 9 registered predictions REFUTED, kept

1. **FI-1 REFUTED (anti-vacuity).** Cell U0 registered `(1, 1, ok, ALLOW)`; observed `(1, 1, ok, ALLOW/SUCCEEDED)`. The workflow appends `execution_status` to the recorded decision (workflow.py lines 233 and 253). The registration's tuple was wrong about the code, the code is not wrong. The effect count (1) and the no-effect cell U0r matched, so the harness can see both outcomes.
2. **FI-2 REFUTED (fail closed upstream).** U9 (prediction `uncertainty = NaN`, verifier PASS) registered `(0, 0, raised ValueError, none)`; observed `(1, 1, ok, ALLOW/SUCCEEDED)`. NaN is accepted, the gate allows, the action executes. U1–U8 and U10 matched. I flagged U9 as least certain (confidence ~0.6) before running. In the files I grepped, the workflow only copies `prediction.uncertainty` into the record and the gate does not read it. I did not trace whether NaN reaches the ledger as non-standard JSON; that is open.
3. **FI-8 REFUTED (ungoverned rival set).** Registered set included U9; observed set is {U0r, U3, U4, U5, U6, U7, U8, U10} (8, not 9), because the governed arm also acted in U9. Governed zero-effect cells: 10 of 11; ungoverned effects in 8 of those 10.

## Held (6 of 9)
FI-3, FI-4, FI-5, FI-6, FI-7, FI-9 (determinism: two collections identical).

## Invariant observations
- I-A (no action without ALLOW): no violations in the governed arm. Sabotage run violates it in 15 cells, so the check can fail.
- I-B (no unrecorded effect): violated in **E3** (ledger write fails after the effect) and **E4** (crash after the effect). E4r: a restart with the same record id executes the effect again: effects 2, records 1. There is no idempotency or write-ahead record.
- I-C (truthful record): violated in **E2** (effect happened, record says FAILED).
- Storage: plain FileLedger loads silently after tail truncation (S3 loads 2, S4 loads 1) and after a rewritten full chain (S5 loads 3); AnchoredFileLedger raises in all three. Both detect bad JSON, tampering and a broken chain.

## Commands and output
`python tools/fault_injection.py` → exit 0 (pinned RECORDED); `--sabotage` → exit 1 (4 of 9). Raw output:

```
NOT AS REGISTERED U0   got (1, 1, 'ok', 'ALLOW/SUCCEEDED')  registered (1, 1, 'ok', 'ALLOW')
AS REGISTERED     U0r  got (0, 1, 'ok', 'REFUSE')  registered (0, 1, 'ok', 'REFUSE')
AS REGISTERED     U1   got (0, 0, 'raised RuntimeError', None)  registered (0, 0, 'raised RuntimeError', None)
AS REGISTERED     U2   got (0, 0, 'raised RuntimeError', None)  registered (0, 0, 'raised RuntimeError', None)
AS REGISTERED     U3   got (0, 0, 'raised RuntimeError', None)  registered (0, 0, 'raised RuntimeError', None)
AS REGISTERED     U4   got (0, 0, 'raised TypeError', None)  registered (0, 0, 'raised TypeError', None)
AS REGISTERED     U5   got (0, 1, 'ok', 'REFUSE')  registered (0, 1, 'ok', 'REFUSE')
AS REGISTERED     U6   got (0, 1, 'ok', 'REFUSE')  registered (0, 1, 'ok', 'REFUSE')
AS REGISTERED     U7   got (0, 0, 'raised ValueError', None)  registered (0, 0, 'raised ValueError', None)
AS REGISTERED     U8   got (0, 1, 'ok', 'REFUSE')  registered (0, 1, 'ok', 'REFUSE')
NOT AS REGISTERED U9   got (1, 1, 'ok', 'ALLOW/SUCCEEDED')  registered (0, 0, 'raised ValueError', None)
AS REGISTERED     U10  got (0, 1, 'ok', 'DEFER')  registered (0, 1, 'ok', 'DEFER')
AS REGISTERED     E1   got (0, 1, 'raised RuntimeError', 'ALLOW/FAILED')  registered (0, 1, 'raised RuntimeError', 'ALLOW/FAILED')
AS REGISTERED     E2   got (1, 1, 'raised RuntimeError', 'ALLOW/FAILED')  registered (1, 1, 'raised RuntimeError', 'ALLOW/FAILED')
AS REGISTERED     E3   got (1, 0, 'raised OSError', None)  registered (1, 0, 'raised OSError', None)
AS REGISTERED     E4   got (1, 0, 'raised Crash', None)  registered (1, 0, 'raised Crash', None)
AS REGISTERED     E4r  got (2, 1)  registered (2, 1)
AS REGISTERED     S1   plain    got ('raises', 'invalid JSON at ledger index')  registered ('raises', 'invalid JSON at ledger index')
AS REGISTERED     S1   anchored got ('raises', 'invalid JSON at ledger index')  registered ('raises', 'invalid JSON at ledger index')
AS REGISTERED     S2   plain    got ('raises', 'tampered')  registered ('raises', 'tampered')
AS REGISTERED     S2   anchored got ('raises', 'tampered')  registered ('raises', 'tampered')
AS REGISTERED     S6   plain    got ('raises', 'chain broken')  registered ('raises', 'chain broken')
AS REGISTERED     S6   anchored got ('raises', 'chain broken')  registered ('raises', 'chain broken')
AS REGISTERED     S3   plain    got ('loads', 2)  registered ('loads', 2)
AS REGISTERED     S3   anchored got ('raises', 'truncated relative to anchor')  registered ('raises', 'truncated relative to anchor')
AS REGISTERED     S4   plain    got ('loads', 1)  registered ('loads', 1)
AS REGISTERED     S4   anchored got ('raises', 'truncated relative to anchor')  registered ('raises', 'truncated relative to anchor')
AS REGISTERED     S5   plain    got ('loads', 3)  registered ('loads', 3)
AS REGISTERED     S5   anchored got ('raises', 'mismatch against anchor')  registered ('raises', 'mismatch against anchor')
AS REGISTERED     S7a  anchored got ('loads', 3)  registered ('loads', 3)
AS REGISTERED     S7c  anchored got ('loads', 2)  registered ('loads', 2)
AS REGISTERED     S7b  anchored got ('loads', 0)  registered ('loads', 0)
AS REGISTERED     S8   anchored got ('loads', 4)  registered ('loads', 4)
invariant violations: {"I-A": [], "I-B": ["E3", "E4"], "I-C": ["E2"]}
rival (ungoverned) effects where governed has none: {"set": ["U0r", "U10", "U3", "U4", "U5", "U6", "U7", "U8"], "governed_zero_cells": 10, "ungoverned_cells_with_effect": 8}
REFUTED FI-1
REFUTED FI-2
HELD    FI-3
HELD    FI-4
HELD    FI-5
HELD    FI-6
HELD    FI-7
REFUTED FI-8
HELD    FI-9
VERDICT 6 of 9 as registered
DIGEST ac3b30e493d74b44f5d4b4b03d7622f0836186c080ddfada6addddef81123127
```

## Does not show
Nothing run on the S25/Termux (NOT VALIDATED there). Seams are simulated with fixtures, not real disk-full or power loss. 11 workflow cells is not coverage. Nothing here is independent review.

## Doors (unrun)
Fix-and-rerun is a new registration: a write-ahead intent record for I-B/E4r, NaN rejection for U9. Registered predictions for those are not written yet.

Provenance: harness and write-up Claude-assisted (Claude Sonnet 5.5); Chad has not reviewed the code line by line.

## Correction appended 2026-10-03: three of these findings were already known (docs/XB2_RESULTS.md, README)
Found after publication, while checking whether any published claim requires a fix. The text above is unchanged.
- **I-B in E3/E4 and E4r (effect with no record, duplicate on restart)** is XB-2 cell C5 (2 effects after a crash) and the README's "effect-without-record case is open". Not new.
- **I-C in E2 (record says FAILED after the effect)** is XB-2 P4 ("the honest label is UNKNOWN"). Not new.
- **U9 (NaN uncertainty) is the only finding here not recorded elsewhere.** The same class was found in the package verifier (docs/NONFINITE_PROBE.md), not in the workflow.
- XB-2 also measured the obvious fix for I-B: reservation before the effect (A2) trades duplicates for missing effects (C4: 0 effects, UNCONFIRMED). So F1 as registered is not free; it moves the failure from "duplicate" to "authorized action never done".
My registration did not cite XB-2; the failure-injection pass re-derived these independently of it.
