# Perplexity — mapping to GSN, W3C PROV and formal methods

> **Author: Perplexity** (external AI analysis), received 2026-10-02 via Chad Holland. Kept **verbatim and unedited** below the line as an external critique. Its claims (about this repository, about philosophy, and its citations) are **not validated** by being stored here; see `docs/EXTERNAL_CRITIQUE_PERPLEXITY.md` for the check. The text arrived with its tables stripped (headings such as "Classification" or "Element-by-Element Mapping" are followed by no table); nothing was reconstructed. sha256 of the text as received: `8139d06b90e850f84f770856e35aeff9a929301ceeb07470e5e61a69530d00ce`.

---

Completed 6 steps
Here is the mapping.
Framing
Sovereign Veritas can be seen as a three-layer composition: GSN supplies the assurance-case shape, W3C PROV supplies the provenance model, and formal methods supply the contract/conformance discipline. SV is not yet a full instance of any one of them. It is a runnable research prototype that partially implements each: a Gate contract instead of a theorem, provenance packages instead of a full PROV graph, and evidence/status judgments instead of a complete GSN assurance case.
1. GSN (Goal Structuring Notation)
What GSN Is
GSN is a graphical notation for assurance cases — structured arguments that a claim about a system is supported by evidence. Its core elements are Goals (claims), Strategies (inference steps), Solutions (evidence references), Contexts, Assumptions, Justifications, and relationships (SupportedBy, InContextOf). The GSN Community Standard defines these precisely (FAA GSN Community Standard V1; NASA — Understanding and Evaluating Assurance Cases).�
Element-by-Element Mapping
Key Structural Difference
GSN builds a hierarchical argument tree: a top-level Goal decomposes via Strategies into sub-Goals, eventually reaching Solutions (evidence). The tree structure allows progressive decomposition and modular argument.�
Sovereign Veritas uses a flat decision procedure: 13 ordered rules applied sequentially to a JSON record. The rules are not hierarchical — they are a pipeline. There is no decomposition of a top-level claim into sub-claims. The system produces a decision (ALLOW/DEFER/REFUSE), not an argument.
The Phase 1 specification moves closer to GSN: its three layers (L1 Computational, L2 Evidence Support, L3 Domain Review) form a hierarchy where L1 is a prerequisite for L2, and L2 is a prerequisite for L3. But even this is a layered pipeline, not a tree — there is no mechanism for decomposing a claim into multiple independent sub-claims and combining their support.
Classification: PLAUSIBLE. SV can be wrapped in a GSN argument, and the Phase 1 specification's layers map naturally to GSN sub-goals. But SV does not itself produce a GSN-style assurance case. It is a decision procedure, not an argument engine. The most useful GSN integration would be to express the top-level Goal "this action is authorized" as a GSN tree where the Gate's 13 rules are Strategies, the evidence package is a Solution, and the known limitations are Assumptions and Defeaters.
2. W3C PROV
What PROV Is
W3C PROV is a data model and OWL2 ontology for representing provenance: "information about entities, activities, and people involved in producing a piece of data or thing, which can be used to form assessments about its quality, reliability or trustworthiness". PROV-O defines classes (Entity, Activity, Agent) and properties (wasGeneratedBy, used, wasDerivedFrom, wasAttributedTo, wasAssociatedWith, actedOnBehalfOf, wasInformedBy).�
Class Mapping
Property Mapping
Key Gap: Field-Level Provenance
PROV tracks provenance at the entity level: which activity generated which entity, which agent is responsible for which entity. SV tracks provenance at the field level: for each runtime field (thermal_status, compute_budget, power_status), the system records where the value came from (MEASURED, OPERATOR, DERIVED, ABSENT, DEFAULTED).
PROV can express field-level provenance if each field value is modeled as a separate entity with its own generation, usage, and derivation relationships. But PROV does not provide a vocabulary for the kind of provenance — whether a value was measured by a sensor, supplied by an operator, computed from other values, or defaulted because nobody provided it. SV's 8-state vocabulary (MEASURED, OPERATOR, DERIVED, INFERRED, ABSENT, DEFAULTED, NEVER_WIRED, UNVERIFIED) is a domain-specific provenance profile that would need to be represented as a PROV profile or extension with SHACL/validation constraints.
The "no implicit promotion" invariant — a default is never reported as a measurement — is a constraint that PROV does not enforce. PROV records provenance; SV checks that the recorded provenance is honest.
Classification: PLAUSIBLE. SV's evidence packages are naturally expressible in PROV-O, and most classes and properties map directly. The gap is that SV's field-level provenance vocabulary and honesty-checking invariant are not native PROV concepts — they would require a PROV profile with additional constraints. The most useful PROV integration would be to export each sv.package/0 as a PROV bundle with per-field entities, enabling interoperation with PROV-compatible provenance systems.
3. Formal Methods
Formal methods is not a single framework but a family of techniques. I map SV to each sub-area separately.
3.1 Formal Specification
3.2 Model Checking
3.3 Theorem Proving
3.4 Information Flow and Authority Separation
The adversary-Gate separation (Adversary ----X----> Veritas Gate) is not a noninterference property. Noninterference requires that the adversary's inputs cannot affect the Gate's output at all. But the adversary is supposed to influence the evidentiary state — the adversary generates challenges and counterevidence that change what the verifier evaluates. Strict noninterference would be false and undesirable.
The correct property is closer to separation of authority: the adversary may influence evidence, but may not directly authorize, mutate registry authority, or bypass the Gate. This maps to:
3.5 Reference Monitor
The Gate is reference-monitor-like, not a full reference monitor. The three classical reference monitor properties (Anderson 1972):
3.6 Design by Contract
3.7 N-Version Programming
The repository is explicit: "N-version, not independent" (tools/verify_package.py module documentation). This is the correct characterization.
3.8 Mutation Testing
3.9 Refinement
4. What SV Composes That Is Novel
SV's contribution is not that GSN, PROV, or formal methods cannot express these ideas. It is that SV composes them into a concrete, runnable package-verification and authorization prototype. The specific integrations:
5. Summary Classification
The Thesis
Sovereign Veritas does not replace GSN, PROV, or formal methods. It composes elements of all three into a single runnable prototype: a Gate contract (from formal methods) that produces evidence packages (from PROV) that can be assessed for epistemic support (from GSN). None of the three frameworks alone provides this integration. The question for the future is whether SV will deepen each layer — adding a GSN argument tree, a full PROV export, mechanized proofs — or remain a prototype that demonstrates the composition is possible and useful.