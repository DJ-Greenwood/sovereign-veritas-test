# G1 recount registration: is each sv.gate/1 item built on main? (nothing run yet)

Status: registration only. Written 2026-10-03 against origin/main (4eda7d4), before `tools/g1_recount.py` exists.
Claude-assisted (Claude Opus 5.5); Chad asked for "a real test-per-item recount", he has not reviewed this text.

**Exploration disclosed (C-EXPLORE).** Before writing this I read `Gate.evaluate` (sovereign_veritas/decision.py),
`RuntimeState`, `Capability`, and grepped `tools/verify_package.py` and `tools/attack_harness.py`. The predictions
below are informed by that reading, so they test whether the reading is right, not a blind guess. An earlier
grep-only count (docs/CLOSURE_DRAFT.md, PR #25) said "at most 1 to 2 of 7"; this replaces it with tests.

## Tests (one per item, from the "what would show it works" column of docs/SV_GATE_1_SCOPE.md where runnable here)

| id | item | test against main | registered result | conf. |
|---|---|---|---|---|
| R1 | G1-1 nav_status | construct `RuntimeState(..., nav_status="LOST")` | raises `TypeError` (no such field): **NOT BUILT** | 0.95 |
| R2 | G1-2 latch in gate + package | count of `latch` (case-insensitive) in `sovereign_veritas/*.py` and `tools/verify_package.py` | 0: **NOT BUILT** as a gate rule or verified package field. Structural check only (weaker than a behavioural test; the SITL replay needs a simulator not available here) | 0.9 |
| R3 | G1-3 consumed token | `python tools/attack_harness.py --round3`, line `A7/D3` | first use ACCEPTED, replay refused: **BUILT** | 0.8 |
| R4 | G1-4 session budget | 20 identical authorized, verified requests through one `Gate`, `policy={"session_budget": {"count": 5}}` | 20 of 20 ALLOW (no budget is enforced; the 6th does not REFUSE): **NOT BUILT** | 0.95 |
| R5 | G1-5 signed grants | count of `allowed_authorizers` in `tools/verify_package.py` and `sovereign_veritas/*.py` | 0: **NOT BUILT**. Structural check only | 0.9 |
| R6a | G1-6 DEFAULTED runtime on ALLOW | `RuntimeState` with only defaults, `metadata={"compute_budget": "DEFAULTED"}`; authorized, verified request | ALLOW (DEFAULTED is not refused): not built | 0.9 |
| R6b | G1-6 missing step_count | `Capability(max_steps=3)`, no `step_count` in metadata | ALLOW (missing count is not refused): not built | 0.95 |
| R6c | G1-6 evidence must be MEASURED/DERIVED | `required_evidence=("fresh",)`, `metadata={"fresh": True}` with no evidence-state tag | ALLOW: not built. R6 = **NOT BUILT** if any of a/b/c ALLOWs | 0.9 |
| R7a | G1-7 chain of 3 | registry c (unauthorized) <- b (authorized, parent c) <- a (authorized, parent b); request a | ALLOW (only one hop is checked): **NOT BUILT** | 0.9 |
| R7b | G1-7 cycle | a (parent b), b (parent a), both authorized; request a | ALLOW (no cycle detection; one hop, no loop) | 0.9 |

**Total registered: G1-3 built; G1-1, G1-2, G1-4, G1-5, G1-6, G1-7 not built. 1 of 7.**

## Anti-vacuity (M3)
`--selftest` runs R4, R6a-c and R7a-b against a stub gate that implements each rule (budget of 5; DEFAULTED,
missing count and untagged evidence refuse; walk the chain, refuse a gap or cycle). Each must flip to REFUSE,
otherwise the test cannot see the rule and the NOT BUILT verdict is vacuous. R1 flips if a stub
`RuntimeState` subclass accepts `nav_status`. R2 and R5 flip if a planted file contains the word. R3's
sabotage is the harness's own D2 row (A7 replay ACCEPTED), which already exists.

## Exit
`RECORDED` pinned after the scored run; exit 0 only on it. `--sabotage` swaps the stub in as the gate
under test, so the verdict tuple changes and the script must exit 1.

## What this cannot show
"NOT BUILT" from R2 and R5 is a word count, not behaviour. "BUILT" for R3 is the harness's own claim
replayed, not a new attack. Nothing here runs SITL or the S25.

## Door (M15)
The registered "what would show it works" tests for G1-1 and G1-2 need SITL; they stay unrun.
