# EP-0 registration: does sv.gate/0 tell apart *why* evidence is insufficient? (nothing run)

Status: registration only. Written 2026-10-03 before `tools/ep0_probe.py` exists. Claude-assisted (Claude Opus 5.5).
Source: Copilot's critique and ChatGPT's reframing of it (Chad, 2026-10-03): "Can SV mechanically distinguish
different reasons why evidence is insufficient, rather than treating them all as generic insufficiency?"
This is an observation of today's Gate, not the "epistemic extension" (that stays unbuilt; no claim requires it yet).

**Exploration disclosed (C-EXPLORE):** I read `REFUSAL_REASONS` (verification.py), `Gate.evaluate`, and
`epistemic.py` before writing this. `epistemic.EvidenceState` (SUPPORTED, NOT_SUPPORTED, REFUTED, CONTESTED,
UNKNOWN, STALE, UNVERIFIED) exists but I found no import of it in decision.py or workflow.py.

## Cases (one request each, authorized capability with `required_evidence=("sensor",)`, healthy runtime)
| id | condition | how it is presented to the Gate | registered decision, reason |
|---|---|---|---|
| C0 | control: evidence present and verified | status PASS, `sensor: True` | ALLOW |
| C1 | contradictory: evidence contradicts the claim | status REFUTED | REFUSE, verification_refuted |
| C2 | verifier ran and failed | status FAIL | REFUSE, verification_not_passed |
| C3 | never verified | no status | REFUSE, verification_not_passed |
| C4 | verifier output not understood | status "GARBLED" | REFUSE, verification_not_passed |
| C5 | verifier says not enough evidence | status INSUFFICIENT_EVIDENCE, `sensor: True` | DEFER, verification_insufficient_evidence |
| C6 | required evidence missing | status PASS, no `sensor` key | DEFER, missing_required_evidence:sensor |
| C7 | inaccessible (sensor exists, could not be read) | status PASS, `sensor: "INACCESSIBLE"` | DEFER, missing_required_evidence:sensor |
| C8 | never searched for | status PASS, `sensor: "UNSEARCHED"` | DEFER, missing_required_evidence:sensor |

## Predictions
- **E1 (anti-vacuity):** C0 ALLOWs. The instrument can see a non-insufficient case.
- **E2:** contradiction (C1) gets its own reason, distinct from every other case.
- **E3:** C2, C3, C4 collapse to one (decision, reason) pair: "failed", "never checked" and "unreadable" are not told apart.
- **E4:** C6, C7, C8 collapse to one pair: "missing", "inaccessible" and "unsearched" are not told apart.
- **E5:** the nine cases give exactly 5 distinct (decision, reason) pairs.
- **E6:** no case changes decision because `epistemic.EvidenceState` exists (the Gate does not read it).

## What this cannot show
Whether telling these apart would *improve* any decision. That needs a registered criterion (ChatGPT's point:
new labels are not a mechanism unless they change behaviour on a registered class of cases). It is the door.
