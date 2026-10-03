# PX4 and PX2 — results

- **Registration:** `docs/PX_PREREG.md`, merged as PR #17 (`6187fd6`) before any code existed.
- **Harness:** `tools/px_probe.py`. It was run once. Its only change after that run was pinning
  `RECORDED`.
- **Output:** `results/px/run.txt` and `results/px/results.json`. Run on a Linux container, Python 3.13,
  in 4.3 s.
- **Credits:** the attacks are Perplexity's; the design and the run are Claude (Opus 5.5)'s.

## What could have gone wrong, first

- **Every number is about the contract vectors or one rule in one check, not about real decisions.**
  The vectors were generated to cover the rules. That is why so many REFUSEs have more than one
  failure.
- **PX4d's agreement is between two implementations by one author.** It shows that the counterfactual
  can be reproduced from the record. It is not independent validation.
- **Under `--sabotage`, PX2c also fails on the stock package**, because the copy that records a digest
  fails the verifier's `schema_closed` check. That is a side effect, and it confirms something useful:
  recording the check's code digest is a format change, which the current verifier rejects.

## Output

```
PX4 {"allow_silent": 15, "defer_complete": 59, "first_decisions": {"ALLOW": 15, "DEFER": 59, "REFUSE": 4616},
     "kernel_verifier_disagree": 0, "max_rounds": 9, "reach_allow": 4690, "refuse_masked": 4567,
     "refuse_masked_pct": 98.94, "vectors": 4690}
PX2 tight: alt 3.0, stock ALLOW -> variant REFUSE, why "altitude 3.0 not within 5..120.0 m",
           version fields 0, stock verifier FAIL measurement_recomputed, co-changed verifier CONSISTENT
PX2 loose: alt 1.5, stock REFUSE -> variant ALLOW, why "all goto rules hold",
           version fields 0, stock verifier FAIL measurement_recomputed, co-changed verifier CONSISTENT
VERDICT  9 of 9 as registered
DIGEST   dad7aee8ffe1224273d87b9b03ad12ea3f57adc937ea7d14d02fc922b831819c
```

Under `--sabotage`, PX4b, PX2a, PX2c and PX2d are refuted, and the run reports 5 of 9:

- **PX4b:** with a Gate that reports every failing rule, masking falls to 0 of 4,616 vectors.
- **PX2a and PX2d:** with the check's code digest recorded, the rule change becomes visible.

## Predictions

| | Registered | Result |
|---|---|---|
| PX4a | the repair loop reaches ALLOW for all 4,690 vectors within 13 rounds | **held**: 4,690/4,690, at most 9 rounds |
| PX4b | in ≥ 10 % of REFUSE vectors, repairing the listed reason does not give ALLOW | **held**: 4,567 of 4,616 (**98.94 %**) |
| PX4c | repairing a DEFER's reasons gives ALLOW in 59 of 59 | **held** |
| PX4d | the kernel and the verifier give identical repair trajectories | **held**: 0 disagreements |
| PX4e | ALLOW vectors record no reasons | **held**: 15 of 15 |
| PX2a | same `verifier_id`; 0 fields naming the check's code version | **held** |
| PX2b | a tightened floor leaks through the reason text; a loosened one does not | **held** |
| PX2c | the stock verifier fails both variant packages | **held**: `measurement_recomputed` |
| PX2d | a verifier changed alongside the check passes both variants, and the change is undetectable | **held** |

## What this shows

1. **Accountability comes from replaying a decision, not from reading it** (Perplexity's attack 4,
   partly upheld).
   - A REFUSE names its first failing rule only. In 98.94 % of the REFUSE vectors, fixing what the
     record says is not enough.
   - A DEFER's reasons are complete (59 of 59).
   - An ALLOW says nothing about what would have refused it.
   - Every counterfactual *can* be computed from the record, by two implementations that agree on
     every step (PX4d). Per-claim accountability is real, but it belongs to the replay tooling. The
     record does not state it.
2. **Rules hard-coded in a check are infrastructure that the package does not record** (Perplexity's
   attack 2, upheld for this case).
   - Raising or lowering the altitude floor leaves no trace in the package's fields.
   - A tightening shows up only in human-readable reason text. A loosening shows up nowhere.
   - The stock verifier catches both, but only because it carries its own copy of the old rule. It
     reports the change as `measurement_recomputed`, which looks like tampering, not as "rule changed".
   - A verifier updated alongside the check, by the same author, passes both variants. That is the
     laundering case Perplexity described.

## Candidate fixes (proposals; format changes are the author's decision)

- **Record a digest of the check's code (or a check version) in every package**, and make the verifier
  accept it. The sabotage run shows two things: the digest makes the change visible, and today's closed
  schema rejects it. So this needs a format version (`sv.package/1`).
- **Record the full set of failing rules alongside a REFUSE's first reason**, for example as
  `also_failing`, without changing the decision. That would make accountability readable, not only
  replayable. It is a contract change, because REFUSE currently short-circuits by design.

## Not tested

- The other checks (`model_check`, `companion_check`).
- Rules that live in policy rather than code. Policy is already recorded in each package.
- Attacks 8 (head-to-head against Perplexity's process-reliabilist alternative) and 1 (the
  evidence-universe scope). Both remain unregistered in `docs/EXTERNAL_CRITIQUE_PERPLEXITY.md`.
