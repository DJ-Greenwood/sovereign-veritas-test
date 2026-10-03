# External adversarial analysis — Perplexity (2026-10-02)

## Provenance

**Author: Perplexity**, an external AI system. Chad Holland received three analyses on 2026-10-02 and
brought them into this repository. They are stored verbatim and unedited in `docs/external/`:

| File | What it argues |
|---|---|
| `perplexity_2026-10-02_strongest_opposite.md` | the strongest opposite architecture to Sovereign Veritas |
| `perplexity_2026-10-02_repository_analysis.md` | an analysis of this repository |
| `perplexity_2026-10-02_gsn_prov_formal_mapping.md` | how SV maps to GSN, W3C PROV and formal methods |

Each file records the sha256 of the text as received. The texts arrived with their tables stripped,
and no table has been reconstructed.

The analyses are **an external critique, not this project's position**. They are not rewritten into
the project's voice. Their claims are hypotheses until checked. That applies to their philosophical
claims and to their citations, which have not been re-verified here.

This record is unrelated to the "Dependent Evidence" proposal behind V14, whose drafter is still
INDETERMINATE (`docs/LINEAGE.md`). The two are kept apart.

**Summary record** (wording from Chad Holland):

> **External adversarial analysis — Perplexity.**
> - **Proposed strongest opposite architecture:** Process-Reliabilist Decision-Theoretic Monism.
> - **Primary attack:** SV may relocate rather than eliminate epistemic assumptions, particularly
>   through corpus construction, ontology, selector policy and authorization boundaries.
> - **Primary counterargument identified by Perplexity:** integrated process-level reliability lacks
>   SV's per-claim accountability and its structural resistance to motivated evidence selection.

## Perplexity's factual claims about this repository, checked against the repository

Checked by Claude (Opus 5.5) on 2026-10-02 at `main` `1d14536`.

| Claim | Check | Status |
|---|---|---|
| 4,690 contract conformance vectors | `contract/gate_vectors.jsonl` has 4,690 lines | **SUPPORTED** |
| "185 tests passing" | That figure is the README's S25 row, recorded at `5b64d8e`. The current suite in the container is 444 passed, 1 skipped. | **SUPPORTED as a quote of a dated README row**; stale as a description of today |
| "22/22 verifier guards killed" | `docs/INTEGRATION.md` records 22/22. Later runs record 25/25 (`docs/VEHICLE_ACTION.md`), and a CI-equivalent run on 2026-10-02 killed 27/27. | **Stale** |
| The Gate does not read evidence-state tags (F1) | `docs/INTEGRATION.md` F1; `decision.py` has no reference to `evidence_states` | **SUPPORTED** |
| No reference to GSN, W3C PROV, Dung or AGM | no `.md` file in the repository mentions them | **SUPPORTED** |
| The Phase 1 `EpistemicAssessment` type is "not established" as implemented | `sovereign_veritas/epistemic.py` defines `EpistemicAssessment`, `Contestation`, `VerifierIndependence` and related types, and tests use them. `package.py` and `tools/verify_package.py` do not include them, so they are not in packages and not covered by `package_digest()`. | **Partly wrong**: the types are implemented; integrating them into packages is not |
| X4 (race) and X5 (write failure) are open | `docs/EXECUTION_BOUNDARY_RESULTS.md` | **SUPPORTED** |
| No systemwide threat model; per-challenge models exist | `CHALLENGE.md`, the V14 registration; no global model document | **SUPPORTED** |

## Where Claude disagrees with Perplexity's argument

These are disagreements, recorded next to the critique rather than edited into it.

1. **"Process validation is empirically testable; per-claim independence is not."** This holds for
   *neutrality*. It does not fully hold for *independence*.
   - Shared ancestry can be detected structurally whenever lineage is recorded. V14g and V15 case 4
     test exactly where that stops: an undeclared common root.
   - What cannot be tested from inside the system is whether the evidence universe is adequate.
2. **"Missing evidence leaves the prior unchanged."** This is false in general. A search that was run
   and returned nothing is informative; a search that was never run is not. This is exactly the
   distinction between ABSENT and NEVER_WIRED that Perplexity's opposite architecture collapses.
3. **"Relocation is worse than transparency."** This is an empirical claim, and nobody has measured
   it. Attack-surface item 2 below is the test.
4. **The internalist/externalist framing.** It is useful, but it presents a choice that need not be
   exclusive. A system can record per-claim lineage *and* be calibrated as a process. Whether
   doing both is worth the cost is attack-surface item 8.

## Perplexity's attack surface turned into a test plan

The attack surface is the most useful part of the critique. For each item: what this repository
already has, what it lacks, and a falsifiable experiment. **None of these experiments is registered
yet.** Each needs its own registration before any code.

| # | Attack (Perplexity) | Already in evidence | Gap | Proposed experiment (unregistered) |
|---|---|---|---|---|
| 1 | Evidence-universe assumptions (the closed-world trap) | EL-007 (evidence-ledger): the closed-world trap was registered and observed | A package cannot state what was *not* searched | **Omitted-evidence probe**: build a package whose evidence universe excludes the decisive contrary record. Predict ALLOW + CONSISTENT, and zero fields stating the universe's scope. Then add a scope declaration and test whether the verifier can check it at all. |
| 2 | Corpus/ontology bias ("epistemic laundering") | The Gate's policy is recorded in each package and verified | The *check* (for example `vehicle_check`) is named by `verifier_id`, not by a digest of its code; its rules are infrastructure, not claims | **Laundering test**: the same inputs under two check versions that differ in one rule. Predict that the packages differ only in the decision. Measure whether a reader can tell from the package *which rule* changed. If not, the ontology is invisible, and Perplexity's point holds here. |
| 3 | An independent selector is not a neutral one | V14 (adversarial error within E), V14g (common root), V15 case 4 (derived B, MAC'd) | Independence is recorded as a label | Covered by V15, now registered. Extension: an independent B with a systematic bias of less than L, scored for undetected breach. |
| 4 | Per-claim accountability, claimed as SV's advantage | Each package can be re-checked; V15g registers that no recovery links back to the approval it replaces | It is untested whether a package can answer "what input would have refused this?" | **Counterfactual flip set**: for every contract vector, compute the minimal input changes that flip the decision. Predict the set is computable from the package alone for all 4,690 vectors, which is cheap because there are 13 ordered rules. A failure means accountability is narrower than claimed. |
| 5 | Distribution shift | none in SV | SV has no notion of a reference distribution | **Shift probe on the outcome loop** (Principia note064/note065 machinery): does the corpus-independent selector surface shift earlier than a calibration-only monitor? Perplexity predicts yes; register that prediction and let it fail. |
| 6 | Motivated reasoning | EL-007: the generator's non-control of evidence selection was measured (10 of 11 as registered) | Only one generator and one task family | Rerun EL-007 with a prompted-to-conclude generator and a calibration-only baseline side by side. |
| 7 | Calibration versus provenance | Principia note064 (outcome-feedback loop with a bootstrap confidence gate, 9/10, P5 refuted) | SV records provenance and never calibration | Attach calibration as a recorded, separately verified field. It must never be promoted into evidence; this mirrors the "no implicit promotion" rule for model confidence. |
| 8 | Does evidence conservation add measurable value? | nothing head to head | This is the test that could falsify the architecture | **Head-to-head**: SV (separated selection, conserved evidence) against Perplexity's process-reliabilist baseline (integrated, calibrated, evidence absorbed). Use the same tasks under stationarity, under shift and with a motivated generator. Pre-register what would count as SV adding *no* value: equal per-claim error detection at higher cost in all three regimes. |

**Recommended order:** items 4 and 2 first (cheap, deterministic, they test SV's own claims), then 8
(the decisive one, and expensive), then 1.

## Credit

- The critique is Perplexity's.
- The check of its factual claims, the disagreements and the test-plan mapping are Claude
  (Opus 5.5)'s.
- The summary record and the decision to keep the critique intact are Chad Holland's.
