# Closure criterion for a sovereign-veritas version: DRAFT for Chad's review

Status: Speculative. Draft written 2026-10-03, Claude-assisted (Claude Sonnet 5.5), from a criterion Chad pasted (ChatGPT-sourced) and Claude's review of it. Not adopted. It is not part of METHOD.md; adopting it is a change under M18.

## The criterion (a version is closed when all six hold)
1. **Every registered prediction has a disposition:** SUPPORTED, REFUTED, UNDECIDED, or CUT. CUT needs a written reason, is append-only, and may not be applied to a REFUTED claim to hide it (M8).
2. **Every discovered failure is fixed, or accepted as a stated boundary, or out of scope.** "The system does not guarantee this" is a valid disposition, written in the README.
3. **Every item of the version's declared gate has a disposition.** For sv.gate/1 that is G1-1 to G1-7 (docs/SV_GATE_1_SCOPE.md).
4. **Attack rounds stop producing new failure classes.** Concretely: N consecutive pre-registered rounds, each adding at least one new attack, produce no new class. N is fixed before the rounds (proposal: 3). Failures are counted by equivalence class (many attacks reducing to "no external freshness anchor" are one class).
5. **Independent attack.** Two independent humans, or one documented reviewer plus a rerun, given the claims, code, registered experiments, failures and boundaries, and asked for a counterexample, find no new in-scope class. A review by the author or by an AI is not this.
6. **No fix without a requiring claim.** A fix is built only if a registered claim, a G1 item, or a published README claim is violated without it. Otherwise it is documented and left unbuilt.

Further improvements after closure are a new version, not unfinished work.

## Applying rule 6 to F1 to F4 (checked 2026-10-03; reading, not a run)
| fix | violates a published claim? | verdict under rule 6 |
|---|---|---|
| F3 non-finite uncertainty | yes, a refuted registered prediction (FI U9); same class as docs/NONFINITE_PROBE.md | built (PR #24) |
| F1 write-ahead intent | README already states the effect-without-record case is open; XB-2 A2 shows reservation trades duplicates for missing effects | not required by a claim; leave unbuilt unless Chad wants the stronger claim, then register it against XB-2's at-most-once result |
| F2 UNKNOWN instead of FAILED | XB-2 P4 found it and said the honest label is UNKNOWN; I did not check whether a later PR changed the label | check the code on main first |
| F4 duplicate id on restart | sequential case closed (PR #8); restart after a crash is XB-2 C5 | same as F1 |

## Where sv.gate/1 stands (grep of main, 2026-10-03; NOT a verified count)
| item | found on main |
|---|---|
| G1-1 nav_status | no matches for `nav_status` |
| G1-2 latch as gate rule, recorded in package | a latch exists in tools/corridor_challenge.py, vehicle_action.py, sitl_drift_probe.py; not checked whether it is a gate rule or package field |
| G1-3 consumed token | built: tools/consumer.py; scope doc says A7 1 to 0 |
| G1-4 session budget | no matches for `session_budget` |
| G1-5 signed grants | no matches for `allowed_authorizers` |
| G1-6 missing evidence refuses | not searched |
| G1-7 grant chain | not searched |
Reading: at most 1 to 2 of 7 done. Criterion 3 is far from met. A real recount means running a test per item, as the scope doc's "what would show it works" column says.

## Open
Choice of N in rule 4; whether CLOSURE becomes M19 or a CONTROLS.md entry (M17: one definition per rule); what counts as "independent" for rule 5 while only one reviewer (Denzil) exists.
