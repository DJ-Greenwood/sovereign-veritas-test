# External review, 2026-10-03: assessment and prioritized recommendations

## Provenance
Two texts Chad Holland brought in on 2026-10-03. **Author: an external AI system; which one was not stated.**
Stored verbatim in `docs/external/`. External material, not this project's position (C-EXT). This review
was written with Claude (Claude Opus 5.5); Chad has not reviewed it line by line.

| File | sha256 |
|---|---|
| `review_2026-10-03_assessment.md` | `ec700d161872e81de57e8637daf64b18aa80c7be92e978c78951f0ecbf8e0818` |
| `review_2026-10-03_recommendations.md` | `1ad50350085cfef7dc1bd5ae4dac88485e7bdbed46dc7071459c3669cb1421b4` |

Its factual description of the repository matches the README (checked: the negative results, 4,690 vectors,
the DEFAULTED finding, the witness log's limits). Its summary line is a fair statement of scope:
*"A verifiable authorization record for declared inputs, not a system that proves the real-world safety or truth of an action."*

## Recommendations mapped to what exists (reading of main b1501b5, plus one exploratory run)
| recommendation | already in the repo | status |
|---|---|---|
| Execution state machine: durable intent, atomic claim, idempotent executor, UNKNOWN outcome, reconcile | XB-2 measured these mechanisms (docs/XB2_RESULTS.md): reservation alone (A2) and a gateway (A3) trade duplicates for missing effects; only a cooperating idempotent executor (A4) avoided both. XB-2 P4: "FAILED" should be UNKNOWN. FI (docs/FI_RESULTS.md) re-derived the same gaps | **open; the review's design matches what XB-2 found works.** F1/F2/F4 registered, unbuilt (docs/FI_FIX_PREREG.md) |
| Defaults must not satisfy authorization | G1-6 (docs/SV_GATE_1_SCOPE.md); G1 recount R6a: DEFAULTED still ALLOWs | open, scoped |
| Explicit evidence provenance (measured / derived / operator / defaulted ...) | `evidence_states.py` tags runtime fields; the Gate does not read them (EP-0) | partly built |
| Separate VERIFIED / AUTHORIZED / CLAIMED / EXECUTED / OUTCOME_CONFIRMED; no caller-written `authorized=True` / `status="PASS"` | issue #4 B1/B2; G1-5 (signed grants) | open, scoped |
| Independent second verifier, differential tests | Go port of the **Gate** from CONTRACT.md only (C6, 0 mismatches, CI `port-go`), by the same AI-assisted author; no second **package verifier** | partly; not independent |
| Canonical serialization (duplicate keys, NaN, Unicode, -0, null vs absent, sizes) | nesting limit only (`verify_package.py` line 71); `json.loads` otherwise default | **gap confirmed for duplicate keys (below)** |
| Key lifecycle, scope, revocation, threshold approval | ssh-keygen signatures + allowed_signers; no scope/revocation | open; G1-5 covers scope only |
| Expiry, sequence numbers, nonces, policy-version binding | witness log + consumed-token consumer (G1-3) | partly |
| Threat model per component (trusted / authenticated-not-true / untrusted) | **none found** (no "threat model" section outside critique docs) | open; cheap and high value |
| Scope split (core / verifier / execution / adapters / research) | one repository | proposal, not adopted |
| Near-term scope: verifiable decision and execution intent for **reversible** actions | README already disclaims high-consequence use | proposal worth considering |

## Exploratory run: duplicate JSON keys (unregistered, one package, disclosed per C-EXPLORE)
`evidence/sv_package_118a02b75646.json` with a second `"decision"` key inserted **before** the real one (planted REFUSE first, real ALLOW last):
```
dup_first exit=0 VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
```
With the planted key **after** the real one: exit 1, 4 checks failed (package_digest, decision_record_matches,
gate_replay, execution_only_if_allowed). Python's parser keeps the last duplicate (`{"a":1,"a":2}` → `{'a': 2}`),
and the digest is over the parsed object, so the extra bytes are invisible to the verifier. **Consequence:** two
byte-different files verify identically, and a consumer whose parser keeps the *first* duplicate would read a
different decision than the verifier checked. Not yet shown: which real consumer parsers keep the first value, and
whether a signature over the bytes changes anything. This should be registered and fixed (reject duplicate keys)
as its own experiment; it is recorded here so it is not lost.

## Disregarded
Nothing material. The review is grounded; its advice is mostly already scoped, and its two "most urgent" issues
(untrusted-input boundary, non-atomic execution) are the repository's own top negative results.
