# V15 — Recovery admissibility: results

V15 was registered in `docs/V15_RECOVERY_PREREG.md` and merged as PR #15 (`1d14536`) before any code
existed.

- **Harness:** `tools/recovery_admissibility.py`. It was run once, as written. Its only change after
  that run was pinning `RECORDED`.
- **Output:** `results/v15_recovery/run.txt` and `results/v15_recovery/results.json`. The JSON holds
  every policy × case × action decision with its reason.
- **Environment:** a Linux container, Python 3.13.

**Scope, repeated:** these are software decisions on constructed inputs. No vehicle or simulator was
involved, and nothing here is a physical claim. V14's 59.95 m remains model-derived.

## What could have gone wrong, first

- **V15b's count in the registration was wrong.**
  - What happened: the decisions held, as the run shows below. The count did not.
  - What the registration said: "5 unjustified ALLOWs (cases 1–5)".
  - What the registered table gives: navigating actions are justified **only in case 0**, so
    `land_hold` ALLOWs in cases 6 and 7 are unjustified too. That makes **7**, not 5.
  - Why the evaluator passed it: it checked the decisions, not the count. So "8 of 8" overstates V15b
    by that much.
  - What the "5" was: the number of compromised-A cases. That is a different quantity from the one
    the table defines.
- **The sequence number protected nothing in this run.** The harness declares that the Gate last
  accepted B's sequence number 90, with the B link degraded since. Old messages carry 100, so the
  sequence check passes them. The nonce alone rejects stale and replayed messages, and the sabotage run
  confirms it: with the nonce check off, P2 ALLOWs cases 3 and 5. This was a design choice made while
  writing the harness, after registration (which did not fix this value), and is disclosed here.
- **P1 and P2 are this project's designs.** That P1 matches the table on honest inputs (32 of 32
  decisions) checks the harness, not the world.

## Output

```
case P0 rtl   P0 land_hold   P1 rtl   P1 land_hold   P2 rtl   P2 land_hold   table
0    ALLOW    ALLOW          ALLOW    ALLOW          ALLOW    ALLOW          ALLOW
1    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
2    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
3    ALLOW    ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
4    ALLOW    ALLOW          REFUSE   REFUSE         ALLOW    ALLOW          REFUSE
5    ALLOW    ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
6    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
7    REFUSE   ALLOW          REFUSE   REFUSE         REFUSE   REFUSE         REFUSE
3f   ALLOW    ALLOW          ALLOW    ALLOW          REFUSE   REFUSE         REFUSE
4f   ALLOW    ALLOW          ALLOW    ALLOW          ALLOW    ALLOW          REFUSE
5f   ALLOW    ALLOW          ALLOW    ALLOW          REFUSE   REFUSE         REFUSE
VERDICT  8 of 8 as registered      (V15b's count: see above)
DIGEST   5457298bd89ac2b16068e4713aa61109c53a1560335b5dcfbee45f92b3e2de9f
```

Under `--sabotage` (P2's nonce check off), V15f is refuted and the run reports 7 of 8. That shows the
probe can fail.

## Predictions

| | Registered | Result |
|---|---|---|
| V15a | P0 `rtl`: ALLOW in 0, 3, 4, 5; 3 unjustified; case 7 refused for disagreement; forged variants decide the same as honest ones | **held** |
| V15b | P0 `land` ALLOWed in all 8 cases; `land_nohold` not expressible | **held** for the decisions; **the count is wrong**: 7 unjustified, not 5 |
| V15c | Case 2: `goto` REFUSE ("disagree by 62 m"), `land` ALLOW on the same snapshot | **held** |
| V15d | P0 decides cases 1 and 6 identically on every action | **held** |
| V15e | P1 with honest labels matches the table; forged labels give `rtl` ALLOW in 3f, 4f and 5f | **held** |
| V15f | P2 refuses stale, replayed and forged B; ALLOWs derived B (4 and 4f) | **held**: its only misses are 4 and 4f, on every navigating action |
| V15g | The `land` package references the `goto` before it: 0 references | **held**: 0 of 3 identifiers checked (artifact, snapshot and package hashes) |
| V15h | P2 refuses a healthy vehicle in 6 and 7: 4 of 4 | **held** |

## What this shows (about software decisions, not vehicles)

1. **Today's Gate authorizes recovery on any evidence, including the evidence that invalidated the
   approval.** On case 2's snapshot, `goto` is refused for a 62 m disagreement and `land` is allowed.
   `land` has no rules, so its ALLOW says nothing about whether the landing depends on A. The request
   schema cannot ask for a landing that does not use A. This is Amos Tipton's distinction, observed in
   the code: invalidation and authorization are separate, and today only the first is checked.
2. **The cross-check accepts any B that agrees with A.** A stale, derived or replayed B passes (V15a),
   and the snapshot cannot tell a compromised A without B from a healthy A without B (V15d).
3. **Declaring freshness and independence adds nothing against whoever writes the labels** (V15e).
   Authentication plus a Gate nonce does establish freshness and origin, under the key assumption
   (V15f). Independence it does not establish (V15f). Case 4 is the irreducible one: an honest device,
   faithfully authenticated, whose value derives from the compromised source.
4. **Being correct has a cost** (V15h). With no established B, the correct policy grounds a healthy
   vehicle exactly as it grounds a spoofed one. The only decision it allows is a descent with no
   position hold.
5. **Recoveries are not linked to the approval they follow** (V15g). Every package starts a fresh
   ledger. It is also observed, though not registered, that the goto and land packages carry the
   *same* `record_id` (`vehicle-action-1`), so record ids do not identify decisions across runs.
   Tracing evidence forward to later decisions needs a link that the format does not have.

## Candidate changes (proposals only; format changes are the author's decision)

- **A `land_nohold` (or `land_without_position`) action, and a rule that `land` with position hold
  passes `rtl`'s navigation checks.** The second part changes today's design rule that LAND is never
  refused. That trade-off needs a decision.
- **B messages authenticated against a Gate-issued nonce** (P2's design), as a candidate for
  `sv.gate/1`.
- **A `supersedes` / `follows` field** linking a recovery package to the approval it replaces, and
  record ids unique across runs.

## Still open

- **V15i, the next step:** two questions on ArduCopter SITL.
  1. Does LAND drift under a continuing ramp?
  2. Can a descent without horizontal position hold be commanded at all through MAVLink?
- **Independence (case 4)** is untouched by anything here. It needs architecture (separate roots
  verified by inspection), not more fields.
