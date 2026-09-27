# sv.gate/1: scope (2026-09-27; nothing is built yet)

This scopes the next gate version. It does not change sv.gate/0 or any recorded result. The items
come from issue #4 (B1-B3, B5-B7, B9; see `docs/ISSUE_4_RESPONSE.md`), from VEHICLE_ACTION.md (V10,
V12, V13), and from the attack harness (`docs/ATTACK_HARNESS.md`, A7). Each item states what would
show it works, so it can be registered before it is built.

| id | change | why | what would show it works |
|---|---|---|---|
| G1-1 | `nav_status` runtime field (`OK` / `DEGRADED` / `LOST`); `LOST` makes a movement request DEFER, not REFUSE | V10: lost navigation is a state of the vehicle, not a bad request. A DEFER tells the operator "retry when it recovers" | SITL: GPS off → goto DEFERs with `nav_status LOST`; GPS on → the same request ALLOWs. A healthy fix never DEFERs (anti-vacuity) |
| G1-2 | the V13 latch as the gate's disagreement rule, and its state recorded in the package | V12c: a single-reading rule flapped; V13: the latch did not | the V13 ramp replayed from the recorded gaps gives 1 PASS→FAIL and 0 back; the verifier recomputes the latch from the recorded readings |
| G1-3 | consumed execution token: the consumer records every package digest it acted on and refuses a repeat | A7: replaying the latest signed, witnessed package is accepted by D0-D2 (B9) | the attack harness gains a D3 (D2 + consumed set): A7 goes from 1/1 to 0/1; genuine first use stays accepted |
| G1-4 | session budget: a cumulative limit per session and per target (count and total), checked at the gate | each request can pass alone while the sequence does not. The same "drain across turns" pattern is described in Google's zero-trust agents part 2 (Sept 2026) for refunds | a sequence of individually allowed requests whose total crosses the budget: the crossing request REFUSEs and names the budget; a sequence under it all ALLOW |
| G1-5 | B2, B1: authorization and PASS carried as signed statements by allowed keys, not as booleans | the harness showed a signature is what stops forgery; today it covers the whole package, but not *who* granted the capability | a package whose grant is signed by a key not in allowed_authorizers REFUSEs even when the package signature is valid |
| G1-6 | B3, B6, B7: missing evidence refuses (no DEFAULTED runtime on ALLOW; missing `step_count` refuses when `max_steps` is set; required evidence must be MEASURED or DERIVED) | these are the stated limitations of sv.gate/0 | one test per rule that ALLOWs under gate/0 and REFUSEs under gate/1, with the reason named |
| G1-7 | B5: walk the full grant chain; a cycle or gap refuses | one-hop check today | chains of length 1, 3 and a cycle; the cycle and a missing link refuse |

**Order.** G1-3 and G1-4 first: they close attacks the harness can already measure (G1-4 needs a new
attack class, A8 "drain", added to the harness before the rule is built). Then G1-1 and G1-2, which
need SITL. G1-5 to G1-7 change the package schema, so they go together as sv.package/1.

**Not in scope.** Judging intent with a language model, the way the Google post's Semantic Governance
does. That is a useful layer, but its verdict cannot be recomputed by a verifier, so here it would
enter only as recorded evidence (like `model_action`), never as the gate itself.
