# PX4 and PX2 — two of Perplexity's attacks, tested against SV's own claims: registration

Status: **Registered** (2026-10-02), before any code for either experiment was written. The harness is
`tools/px_probe.py`. Results will go in `docs/PX_RESULTS.md`. This file is not edited after the run.

**Origin.** The attacks are items 4 and 2 of Perplexity's attack surface. The full texts are in
`docs/EXTERNAL_CRITIQUE_PERPLEXITY.md` and `docs/external/`. The experiment designs and predictions
are by Claude (Opus 5.5).

**Scope.** Both experiments are software experiments on this repository's own decision procedure and
package format. They make no claim about the world.

---

## PX4 — per-claim accountability: does a decision record say what would have changed it?

Perplexity credits SV with "per-claim accountability". The narrower question tested here is whether a
recorded decision tells a reader what would have changed it.

**Inputs.** All 4,690 vectors in `contract/gate_vectors.jsonl`: 4,616 REFUSE, 59 DEFER and 15 ALLOW,
as recorded in the contract.

**Repair table** (fixed here). Each reason type maps to exactly one edit, which sets the offending field
to a value that the rule accepts:

| Reason type | Repair |
|---|---|
| `evidence_invalid` | input digest set to a 64-hex value |
| `verification_not_passed` / `verification_refuted` / `verification_insufficient_evidence` | status set to `PASS` |
| `capability_missing` | a capability authorized for the requested action |
| `capability_not_authorized` | `authorized = true` |
| `capability_parent_*` | parent present in the registry and authorized |
| `action_capability_mismatch` | the action's capability set to the capability's name |
| `runtime_state_unavailable` / `runtime_not_healthy` | `normal`, `available`, `stable` |
| `missing_required_evidence:x` | `metadata[x] = true` |
| `evidence_quality_*` | quality set to 1.0 |
| `capability_max_steps_exceeded` / `invalid_step_count_metadata` | `step_count = 1` |
| `policy_invalid` / `action_not_permitted_by_policy` | `allow_only` set to a list containing the requested action |

A reason type outside this table stops the run as **COULD NOT RUN**.

**Predictions:**

- **PX4a (anti-vacuity: the repair table is complete).** Applying "repair every listed reason,
  re-decide" repeatedly reaches ALLOW for all 4,690 vectors, within at most 13 rounds.
- **PX4b (REFUSE explanations are incomplete).** Repairing only the reasons a REFUSE lists does not
  give ALLOW in at least 10 % of REFUSE vectors. In those vectors a second failure was masked, because
  REFUSE short-circuits.
- **PX4c (DEFER explanations are complete).** Repairing every reason a DEFER lists gives ALLOW in 59 of
  59 DEFER vectors. DEFER accumulates its reasons, and a REFUSE condition later in the rule order would
  have returned REFUSE instead.
- **PX4d (the counterfactual can be computed from the package by another implementation).** The kernel
  Gate and the verifier's independent re-implementation (`tools/verify_package.py`, through
  `gate_contract.py`'s verifier path) give identical results for every repair step on every vector.
- **PX4e (ALLOW states no counterfactual).** All 15 ALLOW vectors record an empty reason list. The
  record gives no direct account of what would have refused them, although PX4d shows that a reader
  can compute one.

**Sabotage** (`--sabotage`). The probe uses a Gate patched to report every failing rule instead of
only the first REFUSE. PX4b must then fail, which shows that the masking measurement can return null.

**What a result means.** If PX4b holds, then "the package says why it refused" is true only of the
first failing rule. Per-claim accountability then comes from *replaying* the decision, not from
*reading* it. That is still an advantage over the process-reliabilist alternative, but a narrower one
than Perplexity claimed.

---

## PX2 — epistemic laundering: is a rule change visible in the package?

Perplexity claims that SV relocates assumptions into infrastructure: "the ontology is not a theoretical
commitment that can be challenged; it is a data model." This experiment tests that claim on one
concrete case.

**The variants.** `vehicle_check` hard-codes an altitude floor of 2 m (`2 <= alt`). That floor is in the
code, not in the request. Two variants are built by patching a copy at runtime; the original is never
edited:

- **V-tight:** floor of 5 m.
- **V-loose:** floor of 1 m.

**The packages.** Two packages are built through `tools/vehicle_action.py`'s own path, with the `fake`
backend (not a vehicle) and the `healthy_air` scenario:

- a `goto` at an altitude of 3 m under the stock check;
- the same request under V-tight;
- a `goto` at 1.5 m under the stock check;
- the same request under V-loose.

**Predictions:**

- **PX2a (no field names the rule version).** In each pair, the stock and variant packages carry the
  same `verifier_id` (`vehicle-command-check-v0`). No field records which version of the check's code
  ran, as a digest or a version number. Count of such fields: 0.
- **PX2b (a tightened rule leaks through its reason text; a loosened one does not).**
  - The V-tight package's `check.why` names the new floor ("not within 5..").
  - The V-loose package's `why` reads "all goto rules hold" and does not mention the floor at all.
- **PX2c (the stock verifier catches both variants, only because it carries its own copy of the
  rule).** Under the unmodified `tools/verify_package.py`, both variant packages fail
  `measurement_recomputed` or `vehicle_check_bound`.
- **PX2d (a verifier changed alongside the check sees nothing).**
  - A verifier copy with its floor patched to match the variant verifies each variant's package as
    CONSISTENT.
  - The rule change is then undetectable from the packages. This is the laundering case: the change
    lives in two pieces of code by one author, and the record does not carry it.

**Sabotage.** The probe adds the check-source digest to the package, as a *candidate fix* run inside
the probe only, not merged into the format. Under sabotage, PX2a's count becomes 1 and PX2d's
undetectability ends. This shows that the probe can see the difference when it is recorded.

**What a result means.** If PX2a and PX2d hold, Perplexity's laundering point holds for SV's check code.
The decision rules that are not in the request are infrastructure that the package does not record.
The candidate fix is to record a digest of the check's code in each package. That fix is a format
change, which is Chad Holland's decision, and it is **not** made here.

---

## Limits stated before running

- **The contract vectors were generated to cover rules, not sampled from real use.** The 10 % threshold
  in PX4b says something about the vector set, not about decisions in deployment.
- **PX2 tests one rule in one check.** Other checks (`model_check`, `companion_check`) may differ.
- **Both verifier paths were written by one author** (PX4d). Agreement between them shows the
  computation is reproducible from the record. It is not independent validation.
