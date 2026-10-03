# External critique — Copilot (epistemic), with ChatGPT's disposition, and the EP-0 observation (2026-10-03)

## Provenance
**Copilot** (an external AI system; model not stated) wrote a critique of this repository; **ChatGPT** wrote a
disposition of that critique. Chad Holland brought both in on 2026-10-03. Stored verbatim in `docs/external/`:

| File | Author | sha256 |
|---|---|---|
| `copilot_2026-10-03_epistemic_critique.md` | Copilot | `5d864b40f77ad9829a6a7a83cde1930d8b22cf637fd9e8cc71d122ee29043bb6` |
| `chatgpt_2026-10-03_copilot_disposition.md` | ChatGPT | `1899e1b0b73551bd303085adcffc16e75181f9099ed4cf632888f812879d1472` |

External material, not this project's position (C-EXT). Review and probe Claude-assisted (Claude Opus 5.5);
Chad has not reviewed them line by line. Not independent review.

## Copilot's factual claims, checked against origin/main 4eda7d4
| claim | check | result |
|---|---|---|
| no "truth" state exists | `adversarial.py` | **holds**: the only truth field is fixed at `truth_status = "UNDETERMINED"` |
| SV does not distinguish contradictory / missing / inaccessible / unsearched | EP-0 probe below; `epistemic.py`, `evidence_states.py` | **partly wrong.** The vocabulary exists (`epistemic.EvidenceState`: SUPPORTED, NOT_SUPPORTED, REFUTED, CONTESTED, UNKNOWN, STALE, UNVERIFIED; `evidence_states`: MEASURED, OPERATOR, DERIVED, INFERRED, ABSENT, DEFAULTED, NEVER_WIRED, UNVERIFIED). The **Gate** tells contradiction apart, but collapses the others (EP-0) and does not read `epistemic.py` at all |
| records are flat, not a graph | `provenance.chain` in packages | **holds for SV**: a hash-linked list (session-start, then the action). The separate evidence-ledger repo's EL-007 verdict counts distinct supporting/refuting roots; not checked here |
| evidence-selection independence cannot be mechanically enforced | | **not shown.** It is not enforced in SV today; "cannot" in principle is not established (ChatGPT's correction, adopted) |
| novelty is the epistemic framing | | **UNDECIDED**: needs a prior-art search, not intuition |

## EP-0: what the real Gate tells apart (registration docs/EP0_PREREG.md, 7997c67, before the probe)
```
C0  ALLOW  -                                          AS REGISTERED
C1  REFUSE verification_refuted                       AS REGISTERED
C2  REFUSE verification_not_passed                    AS REGISTERED
C3  REFUSE verification_not_passed                    AS REGISTERED
C4  REFUSE verification_not_passed                    AS REGISTERED
C5  DEFER  verification_insufficient_evidence         AS REGISTERED
C6  DEFER  missing_required_evidence:sensor           AS REGISTERED
C7  DEFER  missing_required_evidence:sensor           AS REGISTERED
C8  DEFER  missing_required_evidence:sensor           AS REGISTERED
distinct (decision, reason) pairs: 5 of 9 cases
decision.py/workflow.py import epistemic: False
HELD    E1
HELD    E2
HELD    E3
HELD    E4
HELD    E5
HELD    E6
VERDICT 6 of 6 as registered
DIGEST 0b91d8b0631d964206e3c647e2c62117d582a374ee9d470218bdc8af0781957d
```
`--sabotage` (every case fed as the control) exits 1.

**Observation.** Nine conditions give **5** distinct (decision, reason) pairs.
- **Told apart:** contradiction (REFUTED, its own reason); "verifier says not enough evidence" (DEFER); a missing required item (DEFER, names the item).
- **Collapsed:** "verifier failed", "never verified" and "unreadable verifier output" give the same REFUSE reason. "Missing", "inaccessible" and "never searched" give the same DEFER reason: any value other than the boolean `True` counts as missing.
- **Not wired:** the richer vocabulary in `epistemic.py` is not read by the Gate.

**Limits.** The predictions were written after reading the code (disclosed), so 6 of 6 mainly confirms the reading.
This shows what is collapsed, not that collapsing is wrong: every collapsed case already fails closed (REFUSE or DEFER).

## Disposition (ChatGPT's table, kept where checked)
- Closed-world limit ("internally consistent is not externally true"): **supported as a stated boundary**; the README already says the verifier checks consistency, not that the recorded world is true.
- Build the epistemic extension or an evidence graph now: **not justified.** No registered claim fails without them (rule 6 in docs/CLOSURE_DRAFT.md, PR #25).
- New labels alone are not a mechanism (ChatGPT): a distinction counts only if it changes a decision on a registered class of cases.

## Door (M15), unregistered
Is there a registered case where telling "inaccessible" or "unsearched" apart from "missing" should change the
decision (for example DEFER-and-retry vs REFUSE)? If one exists, that is EP-1. If none, the collapse is a
documented simplification, not a defect.

## Addendum 2026-10-03: two more Copilot messages and two more ChatGPT dispositions
Stored verbatim in `docs/external/`:

| File | Author | sha256 |
|---|---|---|
| `copilot_2026-10-03_worth_pursuing.md` | Copilot | `c1ab3ecdac47c27da1426b01188270c0ddf11eb0b1e764e34455dbac28809819` |
| `copilot_2026-10-03_next_move.md` | Copilot | `e6ed3f965849a7103392a25db6f78c1240d7904dad2457ee063081a708f7bda7` |
| `chatgpt_2026-10-03_novelty_disposition.md` | ChatGPT | `d8729af33b4bdd5bcd5382d3ff86dac646fc202391c8cc3a44c488ae39bc4b30` |
| `chatgpt_2026-10-03_ep1_proposal.md` | ChatGPT | `97f7ebb24c1172ffc0d60e8ee24335a897b01b9a7d3d638e4a0fa90e98eaecba` |

- **Copilot's novelty claims are unverified and are not adopted:** "almost nobody is working on that", "the seed of a new field", "no existing assurance system can do". These are prior-art claims with no search behind them.
  Stated precisely, "the generator cannot influence which evidence is selected" is an information-flow (noninterference) property, a field with prior work; whether it has been applied to evidence selection for AI actions is UNDECIDED pending a literature search.
- **ChatGPT's EP-1 was already run, in another repo.** evidence-ledger's EL-007 (merged 2026-10-02) tests generator-controlled vs separated evidence selection: favourable-only search, suppression, fabricated citations, biased vocabulary, one authorized channel (S1L), and the closed-world trap (P10). 10 of 11 as registered; P3 refuted and kept. Neither AI knew it existed.
- **Its unrun door D1 was run on 2026-10-03** (evidence-ledger PR #4): when the claim key is derived from the generator's wording, an unknown paraphrase turns all 475 refutations into UNRESOLVED, and a generator-named key turns 751 claims SUPPORTED. 6 of 7 as registered; Q4 refuted (kept).
- **Still not tested anywhere:** inaccessible, never-searched and outside-domain evidence, the cases EP-0 shows the SV Gate collapses. EL-007 is not wired into SV's Gate.
