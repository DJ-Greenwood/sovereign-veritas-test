# G1 recount results: sv.gate/1 is 1 of 7 built on main

Registration: docs/G1_RECOUNT_PREREG.md (0cb5458), committed before tools/g1_recount.py existed.
Run against origin/main 4eda7d4, x86-64 container, Python 3.13.15. **NOT VALIDATED on the S25.**
Claude-assisted (Claude Opus 5.5); Chad has not reviewed the code or this text. Not independent review.

## Failures and limits first
- No registered prediction failed (7 of 7 as registered). That is weak news, not strong: the predictions were written after reading the code (disclosed in the registration), so this mainly confirms the reading.
- **R2 and R5 are word counts, not behaviour.** "NOT BUILT" there means the word is absent from the kernel and verifier.
- **R3 replays the attack harness's own round-3 claim** (A7 replay refused under D3). It is not a new attack.
- **G1-1 and G1-2 need SITL** for the test the scope doc registered; only the structural part ran here.
- R6c's stub uses an `evidence_states` metadata key I invented for the stub; sv.gate/1 has not specified where evidence states live.

## Result
```
R1  NOT BUILT  registered NOT BUILT  TypeError: RuntimeState.__init__() got an unexpected keyword argument 'nav_status'
R2  NOT BUILT  registered NOT BUILT  'latch' occurrences: 0
R3  BUILT      registered BUILT      A7/D3 2 first use ACCEPTED, replay refused
R4  NOT BUILT  registered NOT BUILT  ALLOW 20 of 20; 6th = ALLOW
R5  NOT BUILT  registered NOT BUILT  'allowed_authorizers' occurrences: 0
R6  NOT BUILT  registered NOT BUILT  a(DEFAULTED)=ALLOW b(no step_count)=ALLOW c(untagged evidence)=ALLOW
R7  NOT BUILT  registered NOT BUILT  chain of 3 with unauthorized root=ALLOW; cycle=ALLOW
BUILT 1 of 7
VERDICT 7 of 7 as registered
DIGEST 9c9891f14e783deebaf1c00174c777153928b4fdb67412e2ecdb2e14d154bf8e
```
Self-test (anti-vacuity): every NOT BUILT test flips to BUILT when the rule is stubbed in.
```
self-test: 6 of 6 NOT BUILT tests flip to BUILT under the stub: ['R1', 'R2', 'R4', 'R5', 'R6', 'R7']
```
`--sabotage` exits 1.

## What it means
- **G1-3 (consumed token) is the only sv.gate/1 item built.**
- **Behavioural gaps shown by the real Gate today:** 20 of 20 repeated requests ALLOW with no budget (G1-4); a DEFAULTED runtime, a missing `step_count` under `max_steps`, and untagged evidence all ALLOW (G1-6); a three-link chain with an unauthorized root and a two-node cycle both ALLOW, because only one parent hop is checked (G1-7).
- These are the documented limits of sv.gate/0, not new defects. The scope doc already lists them.
- This replaces the grep-only table in docs/CLOSURE_DRAFT.md (PR #25), which said "at most 1 to 2 of 7".

## Door (M15)
G1-1 and G1-2 SITL tests unrun. Per the scope doc's order, G1-4 (with a "drain" attack class added to the harness first) is the next item to register and build.
