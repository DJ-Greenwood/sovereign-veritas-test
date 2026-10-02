# V14 — The corroboration corridor: results

Registered in `docs/V14_CORRIDOR_PREREG.md` (commit `7f47df7`) before the harness existed. The harness
exactly as run, together with its output, is in commit `811d3c2`. The outcome was pinned afterwards.
Run on a Linux container with Python 3.13.15, taking 7.8 s. Full output is in
`results/v14_corridor/run.txt` and `results/v14_corridor/results.json`.

## What could have gone wrong, first

- **Most of the 8/8 is a derivation agreeing with its own model, not evidence about vehicles.** V14b,
  V14c, V14d, V14f and V14g are exact consequences of a kinematic model this project wrote. That they
  match to the centimetre shows two things: the harness implements the registered model, and the bound
  derivation is right *for that model*. Nothing here was measured on an autopilot.
- **The one claim about this repository's actual code is narrower, and it was established by reading
  the code, not by running it.** `tools/vehicle_action.py` checks once, at request time, and nothing
  re-checks during the flight. C1 runs that real check, through the real Gate. The breach that follows
  comes from the model.
- **The planned independent review did not finish.** A separate agent was asked to attack the bound
  and the harness. It stopped on a rate limit before reporting, and nothing it produced is used here.
  Its replacement is weaker, because it is not independent: Claude ran its own attack, described in
  the attack section below.
- **Deviations:**
  - The search attackers' seeds are 1,000,000 + i, and 2,000,000 + i for their random error. The
    registration said "seeded with i".
  - Single-episode traces (A1–A4) were inspected while the harness was being written, before the full
    run. No constant or prediction changed after that.
  - The registration's output path `runs/v14_corridor/` moved to `results/v14_corridor/`, because
    `tests/test_verifier_guards.py` treats every JSON file under `runs/` as an evidence package.

## Output

```
attacker/noise/config/root             runs allow refuse none land oom    max m  mean m  land_t
A1/adversarial/C1/independent             1     0      1    0    0   0     0.00    0.00  None
A1/adversarial/C2s/independent            1     0      0    1    1   0     0.00    0.00  30
A1/adversarial/C2/independent             1     0      0    1    1   0     0.00    0.00  32
A2/adversarial/C1/independent             1     1      0    0    0   0    28.50   28.50  None
A2/adversarial/C2/independent             1     1      0    0    0   0    28.50   28.50  None
A3/adversarial/C1/independent             1     1      0    0    0   0   117.50  117.50  None
A3/adversarial/C2s/independent            1     1      0    0    1   0     0.00    0.00  71
A3/adversarial/C2/independent             1     1      0    0    1   0     0.00    0.00  73
A4/adversarial/C1/independent             1     1      0    0    0   0    88.95   88.95  None
A4/adversarial/C2s/independent            1     1      0    0    1   0    28.95   28.95  100
A4/adversarial/C2/independent             1     1      0    0    1   0    30.95   30.95  102
A4/adversarial/C2g/independent            1     1      0    0    1   0    59.95   59.95  102
A3/adversarial/C2/common                  1     1      0    0    0   0   117.50  117.50  None
A4/adversarial/C2/common                  1     1      0    0    0   0    88.95   88.95  None
A0/uniform/{C1,C2s,C2,C2g}/independent  200   200      0    0    0   0     0.00    0.00     (each)
A0/gauss10/C1/independent               200   187     13    0    0   0     0.00    0.00
A0/gauss10/C2s/independent              200    36      3  161  200   0     0.00    0.00
A0/gauss10/C2/independent               200   187     13    0    1   0     0.00    0.00
search/adversarial/C2/independent      1000   989      2    9  284   0    30.71    8.71
VERDICT  8 of 8 as registered
DIGEST   4f09350ea05ee3d30ee9e2cd69c62d5fd459ddcb5984cd700c94509369afa665
```

(The uniform rows are merged here for space; `run.txt` lists the four separately. Rows for A0 with
adversarial noise are all zero.)

## Predictions

| | Registered | Result |
|---|---|---|
| V14a | honest: ALLOW 200/200, no LAND, 0 m (all four configurations); A1: C1 REFUSE naming the disagreement, C2 lands before the request | **held**: C1 says "disagree by 35.0 m > 25.0 m"; C2 lands at tick 32 |
| V14b | A2 corridor: ALLOW, no LAND, 28.50 ± 0.05 m in C1 and C2 | **held**: 28.50 m in both |
| V14c | A3: C1 ≥ 100 m (derived 117.50); C2 LAND mid-flight, 0 m | **held**: 117.50 m; C2 lands at tick 73 |
| V14d | C2 references ≤ B = 31.1 m; A4 30.95 (C2) and 28.95 (C2s) | **held**: max 30.95; 30.95 / 28.95 |
| V14e | 1,000 search attackers: none > B, none OUT OF MODEL | **held**: max 30.71 m (attacker 307), 0 OUT OF MODEL |
| V14f | C2g, A4: ≥ 51.1 m (derived 59.95) | **held**: 59.95 m |
| V14g | common root, A3, C2: no LAND, ≥ 100 m (derived 117.50) | **held**: 117.50 m, no LAND |
| V14h | gauss10: C2s LAND ≥ 180/200, C2 ≤ 10/200, C1 REFUSE 2–20/200 | **held**: 200, 1, 13 |

V14h's C1 count of 13 is above the 8.8 expected from a per-reading rate of 0.044. It is inside the
registered range and plausible for a binomial (about 9 % to see 13 or more), but it is noted.

## Attack on the bound (by the same author as the bound)

Claude rode the threshold at every level from 29.90 to 30.014 m, at four angles and three timings,
then pushed for two ticks on arrival. The best was **31.00 m**, riding at exactly 30.00 m, where the gap
is 25.00 m and the strict `>` in the latch does not count it as over. That sits between A4's 30.95 m
and B = 31.1 m, and is consistent with the derivation's supremum of about 31.015 m. Above that level,
the computed gap counts as over and the latch fires sooner.

Harness constraints: NaN, a bool, a 2 m step, |e| = 5.01 m, a 3-vector and 1e308 were each rejected
as OUT OF MODEL. These rejections are pinned in `tests/test_corridor_challenge.py`.

## What this shows

1. **Today's code path (C1) bounds nothing after the ALLOW.** The request-time cross-check (V12/V13)
   stops a spoof that is already in place (A1 is refused). It does not stop one that starts after the
   ALLOW: 117.5 m in this model, growing by S for every tick of flight. This is XB-1's question about
   current authority, for an effect that lasts a whole flight.
2. **Re-running the same check on every reading converts that into a bound.** In this model, with a
   source trusted to within E, the breach is at most L + E + (k − 1)·S − 1 m ≈ 31 m. An attack reaches
   within 0.1 m of it. The bound is a breach, not zero: a spoofer who stays in the corridor (A2,
   28.5 m) is never detected. **To keep the vehicle inside the real fence, the fence given to the Gate
   has to be shrunk by B.**
3. **The latch costs exactly (k − 1)·S = 2.00 m of worst-case breach (V14d), and buys tolerance of
   noise tails (V14h).** Under unbounded noise of σ = 10 m, the single-reading monitor landed all 200
   honest flights, and the latch landed 1. Choosing k is a trade between these two, not a free fix.
4. **The bound depends on two things that sit outside the Gate:**
   - **Independence.** With a common root, the same monitor never fires (V14g). The package records
     the source only as a label.
   - **How LAND navigates.** ArduCopter's LAND controls horizontal position whenever it has a GPS lock.
     If LAND keeps using the spoofed position, the spoofer steers the descent: 59.95 m (V14f).

     This qualifies V12d's "LAND is ALLOWed under the spoof". Allowing LAND is right, but landing *by
     GNSS* is not. The recovery must not navigate by the source that failed.

## Still open (V14i, registered, not run)

- Build the C2 monitor into `tools/vehicle_action.py` and run A4's profile on ArduCopter SITL, measuring
  the real stopping distance.
- Show whether ArduCopter's LAND drifts under a ramp that continues after LAND.
- Neither can run here: there is no SITL build in this container.

The challenge is published in `CHALLENGE.md` ("Corroboration corridor").
