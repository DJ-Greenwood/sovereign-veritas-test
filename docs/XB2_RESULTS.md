# XB-2 results — 35/35 cells and 5/5 predictions as registered

Registration: `docs/XB2_PREREG.md` (committed 4a4d02a, before the probe existed).
Probe: `python tools/xb2_boundary_probe.py`. x86-64 container, Python 3.13.15; 25 repeat runs, 0 differing.
`--sabotage` (A4's external system silently stops cooperating): P1 fails, 32/35 cells, exit 1.
**NOT VALIDATED on the S25.** Pinned in CI.

## Failures first

- **New defect in real code (P4).** If an executor performs the effect and then times out, `EvidenceWorkflow`
  records `execution_status = FAILED`, and PR #8's pre-check then refuses the retry. The ledger says the
  effect did not happen; it did. XB-1's X6 tested only failure *before* the effect. "FAILED" is a claim about
  the world that the workflow cannot know; the honest label is UNKNOWN.
- **The real workflow (A1) still duplicates on a crash after the effect (C5: 2 effects)** and on a race
  (C2: 2 effects). PR #8 closed only the sequential case, as registered.
- **Reservation alone (A2) and a gateway (A3) trade duplicates for missing effects.** A crash between
  reservation and effect leaves the authorized action never done (C4: 0 effects, UNCONFIRMED). That is
  at-most-once, measured.

## Transcript (verbatim)

```
XB-2 | effects, final record   (registered in docs/XB2_PREREG.md)
      C0                    C1                    C2                    C3                    C4                    C5                    C6                    
A1    1, CONFIRMED          1, CONFIRMED          2, CONFIRMED          N/A                   1, CONFIRMED          2, CONFIRMED          1, FAILED             
A2    1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          0, UNCONFIRMED        1, UNCONFIRMED        1, UNKNOWN            
A3    1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          0, REFUSED            0, UNCONFIRMED        1, UNCONFIRMED        1, UNKNOWN            
A4    1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          0, REFUSED            1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          
A4n   1, CONFIRMED          1, CONFIRMED          1, CONFIRMED          0, REFUSED            0, UNCONFIRMED        1, UNCONFIRMED        1, UNKNOWN            
cells as registered: 35 of 35
AS REGISTERED      P1 only A4 reaches expected effects + true definitive record in all 7 cases        arms: ['A4']
AS REGISTERED      P2 A4n row equals A3 row (cooperation, not the gateway, gives the guarantee)       equal
AS REGISTERED      P3 A3 differs from A2 only on C3                                                   differs on ['C3']
AS REGISTERED      P4 real workflow C6: effect happened, ledger says FAILED                           A1 C6 = (1, 'FAILED')
AS REGISTERED      P5 no arm records a false CONFIRMED                                                none
VERDICT  35/35 cells, 5/5 predictions as registered
```

## What this answers

Davorin Popović asked where "the durable fact that this exact external effect is permitted to occur once,
under authority that is still current" should live. Measured here, in a model plus the real workflow:

1. **Permission and current authority can be made durable on this side.** An atomic reservation (A2) closes
   the race; a re-check of authority at the execution boundary (A3) closes revocation. That re-check is the
   gateway's *only* measured gain over a reservation inside the workflow (P3).
2. **"Happened exactly once" cannot be made durable on this side alone.** Only A4 — an idempotency key the
   external system honours, plus asking it afterwards — reaches one effect and a true definitive record in
   all seven cases (P1). Against a system that cannot de-duplicate or be asked, A4 degrades to exactly A3 (P2).
   The guarantee comes from the external system's cooperation, not from where the boundary code sits.

So the boundary question splits in two. Where authority is checked is a design choice, and A3 measures its
value. Exactly-once is a property of the pair (authorizing side, external system), and it has to be
established per executor.

## How to read the pass (honestly)

A2–A4n are a reference model written for this experiment. Their rows follow from their definitions; the run
shows the definitions do what the PREREG says and that the probe can fail (`--sabotage`). The A1 row is
measured on the real kernel. This is the textbook at-most-once / at-least-once result made concrete for this
code, not a discovery. No novelty claimed.

## Doors

- Fix P4: record UNKNOWN, not FAILED, when the executor may have acted. Small, but it changes the meaning of
  an existing field, so it is Chad's call.
- Per executor (vehicle, model, companion): can it accept an idempotency key, or be asked afterwards? That
  decides whether A4 is available at all.
- Reservation leases and fencing tokens for multi-process holders. Unrun.
