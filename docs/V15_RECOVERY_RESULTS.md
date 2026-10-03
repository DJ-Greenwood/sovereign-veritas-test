# V15 — Recovery admissibility: results

V15 was registered in `docs/V15_RECOVERY_PREREG.md` and merged as PR #15 (`1d14536`) before any code
existed.

- **Harness:** `tools/recovery_admissibility.py`. It was run once, as written. Its only change after
  that run was pinning `RECORDED`.
- **Output:** `results/v15_recovery/run.txt` and `results/v15_recovery/results.json`. The JSON holds
  every policy × case × action decision with its reason.
- **Environment:** a Linux container, Python 3.13.

**Scope, repeated:** these are software decisions on constructed inputs. No vehicle or simulator was
involved, and nothing here is a physical claim. V14's 59.95 m remains model-derived.

## What could have gone wrong, first

- **V15b's count in the registration was wrong.**
  - What happened: the decisions held, as the run shows below. The count did not.
  - What the registration said: "5 unjustified ALLOWs (cases 1–5)".
  - What the registered table gives: navigating actions are justified **only in case 0**, so
    `land_hold` ALLOWs in cases 6 and 7 are unjustified too. That makes **7**, not 5.
  - Why the evaluator passed it: it checked the decisions, not the count. So "8 of 8" overstates V15b
    by that much.
  - What the "5" was: the number of compromised-A cases. That is a different quantity from the one
    the table defines.
- **The sequence number protected nothing in this run.** The harness declares that the Gate last
  accepted B's sequence number 90, with the B link degraded since. Old messages carry 100, so the
  sequence check passes them. The nonce alone rejects stale and replayed messages, and the sabotage run
  confirms it: with the nonce check off, P2 ALLOWs cases 3 and 5. This was a design choice made while
  writing the harness, after registration (which did not fix this value), and is disclosed here.
- **P1 and P2 are this project's designs.** That P1 matches the table on honest inputs (32 of 32
  decisions) checks the harness, not the world.

## Output

```
case P0 rtl   P0 land_hold   P1 rtl   P1 land_hold   P2 rtl   P2 land_hold   table
0    ALLOW    ALLOW          ALLOW    ALLOW          ALLOW    ALLOW          ALLOW
1    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
2    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
3    ALLOW    ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
4    ALLOW    ALLOW          REFUSE   REFUSE         ALLOW    ALLOW          REFUSE
5    ALLOW    ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
6    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
7    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
3f   ALLOW    ALLOW          ALLOW    ALLOW          REFUSE   REFUSE         REFUSE
4f   ALLOW    ALLOW          ALLOW    ALLOW          ALLOW    ALLOW          REFUSE
5f   ALLOW    ALLOW          ALLOW    ALLOW          REFUSE   REFUSE         REFUSE
VERDICT  8 of 8 as registered      (V15b's count: see above)
DIGEST   5457298bd89ac2b16068e4713aa61109c53a1560335b5dcfbee45f92b3e2de9f
```

Under `--sabotage` (P2's nonce check off), V15f is refuted and the run reports 7 of 8. That shows the
probe can fail.

## Predictions

| | Registered | Result |
|---|---|---|
| V15a | P0 `rtl`: ALLOW in 0, 3, 4, 5; 3 unjustified; case 7 refused for disagreement; forged variants decide the same as honest ones | **held** |
| V15b | P0 `land` ALLOWed in all 8 cases; `land_nohold` not expressible | **held** for the decisions; **the count is wrong**: 7 unjustified, not 5 |
| V15c | Case 2: `goto` REFUSE ("disagree by 62 m"), `land` ALLOW on the same snapshot | **held** |
| V15d | P0 decides cases 1 and 6 identically on every action | **held** |
| V15e | P1 with honest labels matches the table; forged labels give `rtl` ALLOW in 3f, 4f and 5f | **held** |
| V15f | P2 refuses stale, replayed and forged B; ALLOWs derived B (4 and 4f) | **held**: its only misses are 4 and 4f, on every navigating action |
| V15g | The `land` package references the `goto` before it: 0 references | **held**: 0 of 3 identifiers checked (artifact, snapshot and package hashes) |
| V15h | P2 refuses a healthy vehicle in 6 and 7: 4 of 4 | **held** |

## What this shows (about software decisions, not vehicles)

1. **Today's Gate authorizes recovery on any evidence, including the evidence that invalidated the
   approval.** On case 2's snapshot, `goto` is refused for a 62 m disagreement and `land` is allowed.
   `land` has no rules, so its ALLOW says nothing about whether the landing depends on A. The request
   schema cannot ask for a landing that does not use A. This is Amos Tipton's distinction, observed in
   the code: invalidation and authorization are separate, and today only the first is checked.
2. **The cross-check accepts any B that agrees with A.** A stale, derived or replayed B passes (V15a),
   and the snapshot cannot tell a compromised A without B from a healthy A without B (V15d).
3. **Declaring freshness and independence adds nothing against whoever writes the labels** (V15e).
   Authentication plus a Gate nonce does establish freshness and origin, under the key assumption
   (V15f). Independence it does not establish (V15f). Case 4 is the irreducible one: an honest device,
   faithfully authenticated, whose value derives from the compromised source.
4. **Being correct has a cost** (V15h). With no established B, the correct policy grounds a healthy
   vehicle exactly as it grounds a spoofed one. The only decision it allows is a descent with no
   position hold.
5. **Recoveries are not linked to the approval they follow** (V15g). Every package starts a fresh
   ledger. It is also observed, though not registered, that the goto and land packages carry the
   *same* `record_id` (`vehicle-action-1`), so record ids do not identify decisions across runs.
   Tracing evidence forward to later decisions needs a link that the format does not have.

## Candidate changes (proposals only; format changes are the author's decision)

- **A `land_nohold` (or `land_without_position`) action, and a rule that `land` with position hold
  passes `rtl`'s navigation checks.** The second part changes today's design rule that LAND is never
  refused. That trade-off needs a decision.
- **B messages authenticated against a Gate-issued nonce** (P2's design), as a candidate for
  `sv.gate/1`.
- **A `supersedes` / `follows` field** linking a recovery package to the approval it replaces, and
  record ids unique across runs.

## Still open

- **V15i, the next step:** two questions on ArduCopter SITL.
  1. Does LAND drift under a continuing ramp?
  2. Can a descent without horizontal position hold be commanded at all through MAVLink?
- **Independence (case 4)** is untouched by anything here. It needs architecture (separate roots
  verified by inspection), not more fields.

## Lineage of the Amos Tipton A/B recovery challenge (appended 2026-10-03)

There is **one question**: Amos Tipton's public A/B recovery question, preserved verbatim in
`docs/external/amos-tipton_2026-10-02_ab-recovery-question.md`. Two records in this repository's
history test it. They are **not** two independent tests.

An earlier implementation of the same Amos Tipton A/B recovery challenge was registered at `7fb1c48`
and completed at `8e31454`. It is preserved as provenance, but it is not treated as an independent
replication. V15 (`eaacb55`) subsequently formalized and extended the same challenge, and V15 is the
canonical public experiment and results record.

The lineage, in order:
1. Amos Tipton's question (LinkedIn, 2026-10-02).
2. The original A/B experiment, `7fb1c48` → `8e31454`.
3. V15's registration, `eaacb55`.
4. V15's results, `5a1b025`.
5. Later external critique (the next section).

**Where the original A/B experiment is kept.** Branch `experiment/ab-recovery-amos-tipton` is not
merged. Its commits are kept reachable by the tag `archive/ab-recovery-amos-tipton`, which points at
`8e31454`. Its documents are `docs/AB_RECOVERY_PREREG.md` and `docs/AB_RECOVERY_RESULTS.md` at that
commit. Its harness is `tools/ab_recovery_challenge.py`, and its output is in `results/ab_recovery/`.

### What Git establishes

- **Registration** `7fb1c484f5641bbbf859101cf8d5a1dd9cb1fb2a`: committed 2026-10-02 20:14:21 −0500,
  adding `docs/AB_RECOVERY_PREREG.md` only.
- **Results** `8e314544b0c4192f22fed7fd4c29004b858a4c45`: committed 20:16:46 −0500, **2 min 25 s
  later**. It adds the harness, its test, the results document and the run output.
- **Who:** both commits carry the git author "Chad Holland", Claude co-author trailers, and Claude
  session `session_011XCUcZGStMHUv3a3XziMCE`. V15's commits come from a different Claude session,
  `session_01VjYFCynLEBStwNzA7sigYY`.
- **What Git does not establish:**
  - when the harness was written relative to the registration commit;
  - when either commit was pushed.

  Commit times show only that the registration was **committed** first.
- **Reproducibility:** on 2026-10-03, the A/B harness re-run at `8e31454` printed
  `VERDICT 12 of 12 as registered` and `DIGEST a06a43c285be84d87504fba8552489ec1956510f79954f7069fdd28752ca9d47`,
  matching its recorded run. The Gate files it pins (`tools/vehicle_action.py`,
  `sovereign_veritas/decision.py`, `sovereign_veritas/workflow.py`) are unchanged between `facadc2` and
  `main` at `4eda7d4`.

### What the original A/B experiment tested and found

These are the A/B experiment's own findings, as recorded in its results at `8e31454`, summarized here.
**They are not part of V15's result set, and they are not counted as additional evidence for V15.**

**The setup:**
- 9 cases, including 2g. Each was run with the cross-check on and off, against `goto`, `goto` back to
  the fence centre, `rtl` and `land`.
- The real `vehicle_check` and Gate, at `facadc2`.
- Two controls: C0 checked the harness's wiring against `vehicle_action.py`'s `main()`; C2 refused to
  run if the Gate files differed from `facadc2`.

**The findings:**
- **B unavailable versus B stale:**
  - With the cross-check on, unavailable B gave REFUSE for `goto` and `rtl`.
  - Stale B was ALLOWed. Its explicit `xpos_age_s: 600` field and a "STALE" source label were both
    ignored. The stale fix was built to agree with the spoofed A.
  - The A/B results classify this as a specification gap, not an implementation defect.
- **The requester can turn the cross-check off.** Omitting `max_nav_disagreement_m` turned refusals
  in cases 2 and 3 into ALLOWs: a fail-closed bypass by configuration. **This is unique to the A/B
  experiment; V15 always ran with the cross-check on.**
- **EKF GPS-glitch flag (case 2g):** `goto` and `rtl` were refused without needing B. **Unique to the
  A/B experiment.**
- **Full-snapshot replay (case 8):** a pre-spoof snapshot replayed as current was ALLOWed. **Unique to
  the A/B experiment.** V15's case 5 replays only B's message.
- **Refusal information collapses to `verification_not_passed`:** every refusal reached the Gate with
  that single reason. The cause survives only in the check's text inside the package. **Unique to the
  A/B experiment's write-up.**
- **B derived from A** passed the cross-check under a spoof.
- **Prior-approval invalidation was not testable.** No approval state is stored, so cases 5 and 6 were
  byte-identical to 3 and 4, and were recorded as NOT TESTABLE.
- **LAND:** `land` was ALLOWed in every case, with no position evidence, by design. Its dependence on
  GNSS navigation in ArduCopter is the dependency-inheritance concern. The roughly 60 m figure comes
  from V14's model, not from the A/B experiment.
- **Same-author limitation:** one author wrote the A/B registration, harness and classification.

### What was reported to Amos Tipton at the time

Chad Holland's contemporaneous message to Amos Tipton reported the following. It is not quoted here.

- The predictions and matrix were registered before the harness was written, and the registration
  was "pushed before the harness".
- The result was 12 of 12 as registered, not a "pass".
- The findings were as listed above.

That statement about ordering is the author's contemporaneous account. **The repository does not
independently verify it.** Git establishes only the commit order and the 2 min 25 s gap above.

The message's summary "B unavailable: … refused" holds for the cross-check-on configuration. With the
cross-check off, the A/B results show unavailable B ALLOWed. Both appear in the A/B results.

### How V15 relates

- **V15 is a later formalization and extension of the same challenge. It is not an independent
  replication.**
- **V15's registration (`eaacb55`) was produced in a different Claude session, but session separation
  does not establish independence of design.**
  - The V15 case list came from the author at about 21:00, after the A/B results at 20:16.
  - It includes derived-from-A and replay cases that were already present in the A/B experiment.
  - Therefore, independence of V15's design from the A/B experiment is not established, and is not
    claimed.
- **V15 adds:**
  - healthy-A controls;
  - declared-label (P1) and authenticated (P2) policies, with forged variants;
  - a landing without position hold;
  - an admissibility table;
  - a check of the package link between a recovery and the approval before it;
  - a CI-pinned outcome with a sabotage check.
- **The A/B experiment tested things V15 did not:**
  - the cross-check switched off;
  - the EKF glitch flag;
  - full-snapshot replay;
  - the C0 wiring control.

## External critique after the run (appended 2026-10-03)

**Source:** Amos Tipton, Founder & Chief Architect of HYBRID WAYSS, in private correspondence with Chad
Holland on 2026-10-03 after the results were published.

**What follows is an attributed paraphrase, not a quotation.** It does not imply that Amos Tipton or
HYBRID WAYSS endorses, validates or has independently verified this experiment or its results.

His observations, paraphrased by Claude (Opus 5.5) from the correspondence Chad Holland shared:

- **Unavailable versus stale.** The presence of second-source evidence was sufficient for the decision
  even when its age should have been part of it.
- **Specification gap versus implementation bug.** He considers this distinction important for reading
  the results.
- **LAND recovery.** The LAND finding addresses the recovery question directly: what evidence
  justifies a recovery action when that action still depends on the source already considered
  untrustworthy?

**Our factual notes on these observations** (Claude (Opus 5.5); these are not Amos Tipton's statements):

- **Stale B.** In V15, stale B passed only where its value agreed with the spoofed A (case 3). Where the
  stale value disagreed (case 7), it was refused, but for the disagreement, not for its age.
- **No age concept.** No code in the tested path reads B's age. The earlier branch above shows the same
  thing with an explicit `xpos_age_s: 600` that is ignored. Its stale case was also built to agree
  with the spoofed A.
- **Classification.** The earlier branch classifies the stale-B result as a specification gap, not an
  implementation defect. V15 found the same absence ("P0 has no staleness concept"). The Gate
  contract asks for no freshness of B.

**His original public question** is preserved verbatim in
`docs/external/amos-tipton_2026-10-02_ab-recovery-question.md`. The paraphrases of it elsewhere in this
repository, including V15's registration, are not his wording.
