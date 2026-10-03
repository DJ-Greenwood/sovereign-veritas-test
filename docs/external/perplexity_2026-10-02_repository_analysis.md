# Perplexity — analysis of the sovereign-veritas repository

> **Author: Perplexity** (external AI analysis), received 2026-10-02 via Chad Holland. Kept **verbatim and unedited** below the line as an external critique. Its claims (about this repository, about philosophy, and its citations) are **not validated** by being stored here; see `docs/EXTERNAL_CRITIQUE_PERPLEXITY.md` for the check. The text arrived with its tables stripped (headings such as "Classification" or "Element-by-Element Mapping" are followed by no table); nothing was reconstructed. sha256 of the text as received: `d64fd1f834521b7ffd89af5c811bd4dc4dd733876fa6876c2002a2aef162f253`.

---

Completed 15 steps
Now I have everything I need. Here is the analysis.
Sovereign Veritas: Analysis
What It Is
Sovereign Veritas is a research prototype implementing a fail-closed permission gate for AI actions. The central artifact is a decision procedure called the Gate (sv.gate/0): thirteen ordered rules over a JSON record that returns ALLOW, DEFER, or REFUSE. Every decision can be packaged into a self-contained JSON file (sv.package/0) that a separate verifier can re-check from the file alone — importing nothing from the kernel.
The repository reports 185 tests passing, 4,690 contract conformance vectors, 22/22 verifier guards killed under mutation testing, and a 30-second demo that runs on standard library Python. It was built and tested on a Galaxy S25 in Termux, with CI on Linux, macOS, and Windows across Python 3.10–3.14 (GitHub README).
The key insight the repository makes explicit: CONSISTENT means the package agrees with itself and with the Gate's rules. It does not mean the recorded world state is true. This is the distinction between "evidence supports a claim" and "the claim is true" — implemented as a concrete architectural boundary, not a philosophical position.
State Vocabularies (Separated)
The repository uses multiple state vocabularies that serve different purposes. Conflating them would blur the architecture:
"True" appears in none of these vocabularies. The Phase 1 specification states this explicitly: L1 COMPUTATIONAL PASS ≠ TRUTH (PHASE_1_SPECIFICATION.md).
Architecture
The system separates these functions:
Proposer → Candidate → Adversary → adversarial Evidence → Independent Verifier → EvidenceRecord/Ledger → Veritas Gate → ALLOW/REFUSE/DEFER → Executor
The adversary generates challenges and counterevidence but cannot authorize — the authority boundary is explicitly drawn as Adversary ----X----> Veritas Gate (docs/ADVERSARIAL_EPISTEMIC_VERIFICATION.md).
The Gate (sovereign_veritas/decision.py) implements 13 ordered rules: input digest presence, verification status, capability authorization (including one-level parent check), action-capability match, runtime availability and health, required evidence, evidence quality threshold, step count limit, and policy allow-list. A REFUSE returns immediately; DEFER reasons accumulate and do not short-circuit, so an early DEFER does not mask a later REFUSE (CONTRACT.md).
The verifier (tools/verify_package.py) re-implements the Gate logic, all digest computations, thermal classification, and evidence-state validation — using only the Python standard library, importing nothing from sovereign_veritas. It recomputes every digest, replays the Gate from recorded inputs, re-derives thermal status, and rejects claims the format cannot verify (docs/EVIDENCE_PACKAGE.md).
Strengths
1. Honest negative results, published up front.
The README leads with what the system cannot prove. Three failures are documented before any positive result:
A fully consistent rewrite verifies (unsigned).
A slow GPS spoof walked a simulated ArduCopter 61m outside its fence while every check passed.
A repeated record_id causes two external effects and one ledger record.
This is rare. Most systems bury their limitations. Sovereign Veritas makes them the headline.
2. Structural separation is real.
The verifier imports nothing from the kernel. It re-implements the Gate from the documented contract. The contract has 4,690 test vectors and a conformance digest (44823d0f…0628) that any implementation in any language can be checked against. A Go port already produces the same digest (STATUS.md).
3. Evidence-state vocabulary with "no implicit promotion."
The 8-state system (MEASURED, OPERATOR, DERIVED, INFERRED, ABSENT, DEFAULTED, NEVER_WIRED, UNVERIFIED) tracks where each runtime value came from. The invariant is: a default, an operator's word, or an inference is never reported as a measurement. The verifier checks this independently — relabeling DEFAULTED to MEASURED, or OPERATOR to DERIVED, produces a verification failure (sovereign_veritas/evidence_states.py).
4. Mutation testing demonstrates guard load-bearing.
Switching off each verifier guard in turn causes a test failure: 22/22 killed. This is strong anti-vacuity evidence that the current tests exercise those guards — it does not prove the verifier is complete or semantically correct, but it proves the checks are not dead code (docs/INTEGRATION.md).
5. Preregistration before measurement.
The V14 corridor experiment was registered at commit 7f47df7 before the harness existed. The harness was committed at 811d3c2. The outcome was pinned afterwards. This prevents post-hoc modification of predictions — a practice borrowed from experimental science that is uncommon in software engineering (docs/V14_CORRIDOR_RESULTS.md).
6. Phase 1 epistemic assessment specification.
The specification defines a three-layer epistemic model:
L1 Computational Verification: Did the computation execute as specified? (PASS / FAIL / REFUTED)
L2 Evidence Support: Does evidence support the claim? (SUPPORTED / NOT_SUPPORTED / REFUTED / CONTESTED / UNKNOWN / STALE / UNVERIFIED)
L3 Domain Review: Are the assumptions appropriate? (NOT_REVIEWED / REVIEWED / REQUIRES_REVIEW)
Plus Contestation (records disagreement separately from resolution) and Verifier Independence (five dimensions: implementation, method, data, assumption, domain).
The specification explicitly states that L1 PASS does not automatically set L2 to SUPPORTED or L3 to REVIEWED. A computational pass is internal consistency, not evidence support, not domain appropriateness, not truth (PHASE_1_SPECIFICATION.md).
7. LINEAGE.md applies the system's own framework to itself.
The repository tracks influence claims using its own evidence/status system: SUPPORTED, NOT_SUPPORTED, INDETERMINATE. The correction of the Sougata Roy attribution — from "SUPPORTED" to "NOT SUPPORTED" — demonstrates the system working on its own claims. The "Dependent Evidence" proposal provenance is marked INDETERMINATE because "the drafter of the text was not recovered" (docs/LINEAGE.md).
Weaknesses and Open Gaps
1. Single-author implementation.
The repository states this explicitly: "No second, independent implementation exists yet. The kernel and the verifier agree on all 4690 vectors, but both were written by one author." The verifier's own module documentation says it is "N-version, not independent." The Go port was written inside the project. This is the fundamental limitation: structural independence without human independence. The same author wrote both implementations, so they share assumptions, blind spots, and conceptual frameworks (README.md, STATUS.md).
2. The closed-world trap is present and acknowledged.
The V14 corridor experiment demonstrates this concretely. In configuration C1 (request-time check only), a GPS spoof started after the ALLOW is unbounded — the vehicle drifted 117.5m outside its fence. In configuration C2 (re-check on every reading), the breach is bounded at approximately 31m. But this bound depends on the independence of the second position source, and the repository states: "With a common root, the monitor does not fire. The package records the source only as a label." This is exactly the "adversarial evidence flooding" counterexample — twenty sources that all descend from one false origin appear independent unless provenance collapses common ancestry (docs/V14_CORRIDOR_RESULTS.md).
3. Evidence conservation is partial.
The execution boundary problem (XB-1) reveals that execute() runs before the ledger can refuse a record. The sequential case is fixed (PR #8: a known record_id is refused before execution). But two cases remain open:
X4 (race condition): Two threads using the same record_id produce 2 effects and 1 record.
X5 (write failure): The executor succeeds and the ledger write fails, producing 1 effect and 0 records.
The repository explicitly states these are "workflow/ledger limits, not Gate-contract issues" (docs/EXECUTION_BOUNDARY_RESULTS.md). This is honest, but it means the evidence conservation invariant — "reasoning may transform evidence but cannot silently discard it" — is enforceable for sequential known evidence but not for concurrent or failure scenarios.
4. Evidence states are verifier semantics, not authorization semantics.
The Gate does not read evidence-state tags. A DEFAULTED runtime value is counted exactly like a declared value. The tags expose provenance but do not change the Gate's decision. This is documented as finding F1 in docs/INTEGRATION.md. The evidence-state system is informational and auditable — the verifier checks that tags are honest — but it does not influence authorization. A package with DEFAULTED thermal status and a package with OPERATOR thermal status receive the same Gate decision if the values are the same.
This is a design choice, not a bug: the Gate's contract is about authorization, not provenance. But it means the "no implicit promotion" invariant is enforced at the verifier level, not at the decision level. The system can tell you that a value was defaulted; it cannot refuse to act on a defaulted value.
5. No relationship to existing formal methods or assurance case literature.
The repository does not reference GSN (Goal Structuring Notation), Dung argumentation frameworks, W3C PROV, AGM belief revision, or any formal methods literature. The LINEAGE.md document identifies "fail-closed defaults, separation of authorization and execution, reference monitors, separation of duty, independent verification, append-only audit, and idempotent effects" as established prior art (docs/LINEAGE.md). But the system does not map its concepts to these existing frameworks, which means it cannot easily inherit their formal properties or benefit from their maturity.
6. Phase 1 epistemic assessment is specified, not fully implemented.
The PHASE_1_SPECIFICATION.md defines EpistemicAssessment, AssessedEvidenceState, Contestation, and VerifierIndependence as typed, immutable structures. It specifies backward compatibility (existing packages without epistemic remain readable) and tamper detection (epistemic data is included in package_digest()). From the files I inspected, the core implementation files (decision.py, evidence_states.py, verify_package.py) do not show the full EpistemicAssessment type implemented. The specification is the design; the implementation status of these types was not established from the files I examined.
7. No global threat model.
There is no single systemwide adversary model specifying capabilities, goals, access assumptions, and attack surfaces. However, there are local challenge-specific models: the corridor challenge defines attacker limits (1m/tick GNSS movement, 5m independent-position error); the package-verifier challenge defines break conditions; the adversarial epistemic document gives a flow diagram. These are real adversary models, but they are scoped to individual challenges, not to the system as a whole (CHALLENGE.md, docs/ADVERSARIAL_EPISTEMIC_VERIFICATION.md).
8. Thermal policy is uncalibrated.
The S25 thermal limits come from one probe run and are explicitly described as s25-uncalibrated-v0, "not calibrated," and "not a safety claim" (sovereign_veritas/thermal_policy.py).
Mapping to the Theoretical Framework
This repository is a concrete implementation of the concepts we debated in the previous analysis. Here is how each theoretical concept maps:
The Honest Thesis
Sovereign Veritas is not a truth engine and not yet a complete evidence-selection-independence system. It is a research prototype that makes one narrower thing unusually explicit: whether a recorded decision is internally consistent with a declared Gate contract, package bytes, evidence-state tags, an optional signature, and an optional witness log.
Its hardest remaining gaps are:
Human independence — both implementations are by one author
Evidence-world correspondence — the system cannot tell a true input from a false one
Source independence — the common-root problem means "independent source" is a label, not a verified property
Execution atomicity — the race (X4) and write-failure (X5) cases remain open
Global threat modeling — challenge-specific models exist but no systemwide adversary model
What it does that most systems do not: it publishes its negative results first, it separates authorization from verification structurally, it tracks where every runtime value came from, it refuses to call consistency "truth," and it invites independent reimplementations through a frozen contract with 4,690 test vectors. The Phase 1 specification — if fully implemented — would add a three-layer epistemic assessment (computational, evidence support, domain review) with contestation preservation, which would be a genuine contribution beyond what ClaimLedger, GSN, or Dung argumentation frameworks currently offer as integrated systems.
The most useful thing this repository could receive is not another feature. It is a second implementation by someone who has never spoken to the author, written from CONTRACT.md alone.