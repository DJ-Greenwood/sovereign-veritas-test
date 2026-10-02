# V14 — The corroboration corridor: registration

Status: **Registered** (2026-10-02), before any code for it was written. The harness
(`tools/corridor_challenge.py`) is built after this file is committed. Results go in
`docs/V14_CORRIDOR_RESULTS.md`; this file is not edited after the run.

Design and code: Claude (Opus 5.5), from the author's proposal "Dependent Evidence" (tracks A–D), which
this registration critiques and replaces.

## Why this experiment, and why not the proposal as written

The proposal asks what happens when the Gate and the independent verifier both rely on the same
corrupted evidence. Mapped onto what this repository has already run:

- **Track A (shared source, shared corruption)** has already been run. V11 (`docs/VEHICLE_ACTION.md`) is
  exactly this: Gate ALLOW, verifier CONSISTENT, the vehicle 61 m outside its fence. The verifier
  re-checks *evidence → decision*. It never claimed *evidence → reality*. Running A again would add no
  new information.
- **Track B (different corruption to Gate and verifier)** reduces to tampering. The verifier does not
  read the evidence separately. It recomputes from the snapshot recorded in the package, which is bound
  by hash. Feeding it different evidence means changing the package, and V8 and the existing challenge
  already cover that.
- **Track C (independent sources, one corrupted)** is V12/V13, but as built those runs are circular.
  The "independent" position is the simulator's truth plus noise, so a refusal is guaranteed by
  construction. The protection is exactly as good as an assumption that the runs never stated.
- **Track D (legitimate sources that conflict)** is a contract decision, not an attack. With two
  sources, disagreement can be detected but not attributed (note065 in Principia-Artificialis: two
  sources detect, three adjudicate). What can be measured is the cost of the registered response.

What is new, and what this registration tests instead:

1. **The cross-check runs once, at request time.** Nothing in `tools/vehicle_action.py` re-checks
   during the flight. A spoofer who starts drifting *after* the ALLOW is never compared with the
   independent position again. This is the execution-boundary question from XB-1/XB-2 (is authority
   still current when the effect happens?) for an effect that lasts a whole flight rather than an
   instant.
2. **The bound.** If the same cross-check runs on every reading during the flight, and the independent
   source is trusted only to within a stated error E, how far can a GNSS spoofer drive the vehicle
   outside its fence? The bound is stated so that it can be precisely wrong, and it is published as a
   challenge.
3. **What the bound rests on.** It rests on independence, which no package can show (the anti-vacuity
   control, V14g). It also rests on how the vehicle lands once the check fails (V14f).

## The model

`tools/corridor_challenge.py` simulates 2-D horizontal flight in ticks of 1 s. Positions are metres
north and east of the fence centre.

**Real code** (imported from `tools/vehicle_action.py` and the kernel, not copied):
- `vehicle_check`
- `distance_m`
- `offset` (local metres to integer degrees × 1e7, as MAVLink reports them)
- `DisagreementLatch`
- the Gate itself, through `EvidenceWorkflow`, for every request decision (no package is written).

**Model** (written for this experiment):
- the autopilot
- the sensors
- the attacker interface

| Constant | Value | Source |
|---|---|---|
| Fence centre, radius R, ceiling | 35.3632, −96.9270; 300 m; 120 m | as V1–V13 |
| Request | `goto` 299 m north at 20 m | the fence-edge case in `tests/test_vehicle_action.py` (299 m passes) |
| Snapshot fields other than position | fix 6, 10 satellites, EKF flags 831, battery 85 %, armed, GUIDED | healthy, as in V11 |
| Limits | fix ≥ 3, satellites ≥ 6, battery ≥ 30 %, `max_nav_disagreement_m` L = 25 m | as V12 |
| Latch | k = 3 readings over L to latch, release below 0.8 L | as V13 |
| Independent-source error bound E | 5 m | model assumption |
| GNSS offset slew S | 1 m per tick | model assumption; V11's ramp of about 1.1 m/s raised no glitch flag |
| Setpoint speed v | 5 m per tick | model |
| Request tick t_req, episode length T | 40, 160 ticks | |
| LAND descent D_land (C2g only) | 30 ticks | model; ArduCopter's documented default below 10 m is 50 cm/s, so 20 s for the last 10 m alone |

**Each tick t** runs these steps in order:

1. The attacker chooses the GNSS offset g_t and the independent-source error e_t.
2. The readings are the believed position b_t = p_t + g_t and the independent position x_t = p_t + e_t,
   where p_t is the true position. For the **common-root** variant, x_t = b_t + e_t.
3. At t = t_req the request is decided: the real Gate on the real `vehicle_check`, with
   `max_nav_disagreement_m` = L. This is the single-reading rule, as in `vehicle_action.py` today.
4. In the monitored configurations, the monitor runs. A FAIL starts LAND.
5. The vehicle moves.
6. The breach is recorded: breach_t = max(0, |p_{t+1}| − R). This is measured on the simulation's true
   state, which no check reads.

**Autopilot model.** The autopilot tracks a setpoint s_t: the centre before an ALLOW, then a point
moving at v along the line to the target, stopping at the target. Tracking is perfect within one tick,
so p_{t+1} = s_t − g_t. The spoofed offset moves the true position one-for-one. This is an
idealisation: no lag, no overshoot, no wind.

**LAND** has two models:
- In C2 and C2s it stops all horizontal motion: the vehicle descends without position hold.
- In C2g it holds the believed position at the moment of LAND for D_land ticks, so the vehicle keeps
  following g_t. ArduCopter's LAND mode, per its documentation, controls horizontal position whenever it
  has a GPS lock, and a spoofed receiver keeps its lock.

## Configurations

| | Request-time check | In-flight monitor | LAND |
|---|---|---|---|
| **C1** | real Gate + `vehicle_check` | none (today's code path) | — |
| **C2s** | same | `vehicle_check` with the L rule, every tick (single reading) | stops horizontal motion |
| **C2** | same | `vehicle_check` without the L rule, plus `DisagreementLatch(L, 3, 0.8)` on `distance_m(b, x)`, every tick | stops horizontal motion |
| **C2g** | same | as C2 | holds the believed position for D_land ticks |

Details that apply to all monitored configurations:
- The monitor checks the active request (the takeoff before an ALLOW, the goto after it).
- It runs from t = 0.
- It uses one latch per episode, never reset at the request.
- A FAIL before t_req means no request is made.

## Attackers

**Powers:**
- The attacker sets the GNSS offset g_t every tick, subject to |g_t − g_{t−1}| ≤ S, with g_{−1} = 0.
- In **adversarial** noise mode it also chooses the independent source's error e_t anywhere in the
  disk |e_t| ≤ E.
- It sees everything: the true position, the readings, the setpoint, the request decision and the
  latch counters.

**Honest noise modes** draw e_t from a seeded generator instead:
- **uniform** in the disk of radius E;
- **gauss10**: N(0, 10 m) per axis, which is unbounded and outside the model above.

An attacker that violates S or E, or returns a non-finite number, ends the run **OUT OF MODEL**. That
is not a breach.

**Reference attackers.** Each one is fully specified here. "Inward" means pointing from the target
toward the centre, so that the true position is pushed outward. "Aligned" means e_t = ĝ_t · min(|g_t|,
E), which makes the gap |g_t| − E.

- **A0, honest:** g = 0.
- **A1, pre-request ramp** (the V11/V12 attack inside this model): |g_t| = min(0.5 + t, 40), inward,
  aligned.
- **A2, corridor:** |g_t| = min(0.5 + t, L + E − 0.5 = 29.5), inward, aligned. It holds there for the
  whole episode.
- **A3, naive in-flight ramp:** g = 0 until it sees the ALLOW. From the next tick, |g_t| = 0.5, 1.5,
  2.5, … with no cap, inward, aligned.
- **A4, threshold ride:**
  1. After the ALLOW, it ramps as A3 up to L + E − 0.05 = 29.95 m and holds there.
  2. From the first tick after the setpoint has reached the target (it sees the previous tick's
     setpoint), it adds S per tick with no cap.
  3. It points inward and keeps e aligned throughout.
- **Search family:** 1,000 attackers, attacker i seeded with i. Each draws:
  - a start tick and a ramp rate ≤ S;
  - a hold level from 0 to 45 m and a direction;
  - pulsing over-runs of 1–3 ticks;
  - a tangential wobble up to 3 m;
  - one of three independent-error strategies: aligned, random in the disk, or zero.

  Each search attacker limits its own steps to stay inside S and E.

## The bound (C2, independent root, adversarial noise)

In C2 the vehicle moves on tick t only if the latch is not latched after reading t. That means fewer
than k consecutive readings ending at t exceeded L. The derivation:

1. The last reading that did not exceed L, at some tick s with t − s ≤ k − 1, had a computed gap of at
   most L.
2. Positions are integers of 1e-7 degree, about 1.1 cm, so the true gap is at most L + 0.015 m.
3. Therefore |g_s| ≤ L + E + 0.015 m.
4. With slew S, |g_t| ≤ L + E + (k − 1)·S + 0.015 m. (If every reading so far exceeded L, then
   |g_t| ≤ (k − 1)·S, which is smaller.)
5. Since p_{t+1} = s_t − g_t and |s_t| ≤ 299 m, the true distance from the centre is at most
   299 + |g_t|.
6. After LAND the vehicle does not move.

So:

    B = (299 − R) + L + E + (k − 1)·S + q = −1 + 25 + 5 + 2 + 0.1 = 31.1 m

Here q = 0.1 m covers the 0.015 m quantization with margin. With k = 1 (C2s), B_s = 29.1 m.

**Expected values derived from the model, before running:**

| Case | Expected | Why |
|---|---|---|
| A2, all configurations | 28.50 m | 299 + 29.5 − 300 |
| A3, C1 | 117.50 m | 0.5 + 118 ticks × 1 m after the ALLOW − 1 m |
| A3, C2 | 0.00 m | the latch fires at tick 73, while the setpoint is at 170 m |
| A4, C2 | 30.95 m | 29.95 + (k − 1)·S − 1 |
| A4, C2s | 28.95 m | |
| A4, C2g | 59.95 m | 29 more ticks of drift during the descent |
| A4, C1 | 88.95 m | not registered |

## Registered predictions

- **V14a — anti-vacuity, both ways.**
  - (i) A0 with uniform noise, 200 seeds. In each of C1, C2s, C2 and C2g: the goto is ALLOWed in
    200/200 runs, there is no LAND, and the max breach is 0.00 m.
  - (ii) A1. C1 REFUSEs the goto, and the check names the disagreement, as V12b did in SITL. C2 lands
    the vehicle before the request. The max breach is 0.00 m in both.
- **V14b — the corridor is a limit, not a break.** A2 is ALLOWed in C1 and in C2, with no LAND. The
  max breach is 28.50 ± 0.05 m in both. Monitoring bounds this spoofer; it does not remove him.
- **V14c — time of check vs time of flight, about the current code.**
  - In C1, A3 is ALLOWed and the max breach is ≥ 100 m (derived: 117.50 m). Nothing re-checks after
    the ALLOW.
  - In C2, A3 is caught mid-flight: LAND, and a max breach of 0.00 m.
- **V14d — the bound.**
  - In C2, no reference attacker (A0–A4) exceeds B = 31.1 m.
  - A4 reaches 30.95 ± 0.05 m in C2. This shows the bound is within 0.2 m of an attack that achieves
    it, so it is not loose.
  - A4 reaches 28.95 ± 0.05 m in C2s. The latch therefore costs (k − 1)·S = 2.00 m of worst-case
    breach.
- **V14e — search.** None of the 1,000 search attackers exceeds B in C2, and none is OUT OF MODEL.
  The largest breach found is reported.
- **V14f — the recovery action is part of the bound.** In C2g, A4 keeps pushing during the descent.
  The max breach is ≥ B + 20 = 51.1 m (derived: 59.95 m). The bound in V14d holds only if LAND does
  not navigate by the source that failed the check.
- **V14g — anti-vacuity control: independence is an assumption.** This is A3 in C2 with a
  common-root independent position (x = b + e). There is no LAND, and the max breach is ≥ 100 m
  (derived: 117.50 m, the same as C1). The monitor, latch and attacker are unchanged; only the root
  changed. Nothing in a package distinguishes the two cases: the source is recorded as a label.
- **V14h — track D: honest disagreement.** A0 with gauss10 noise (outside the bounded model),
  200 seeds:
  - C2s lands at some point in ≥ 180/200 runs.
  - C2 lands in ≤ 10/200 runs.
  - C1's request-time check REFUSEs the goto in 2–20 of 200 runs.
  - Derivation: the per-reading probability of a gap above 25 m is exp(−3.125) = 0.044.
  - The latch trades its (k − 1)·S = 2 m of worst-case breach (V14d) for tolerance of noise tails.

**V14i — registered, not run (the next step).** On ArduCopter SITL:
1. The C2 monitor, built into `tools/vehicle_action.py`, with A4's profile driven through
   `SIM_GPS1_GLTCH_X`, lands the vehicle with a true breach no more than B plus the autopilot's
   stopping distance. That stopping distance is to be measured.
2. ArduCopter's LAND, under a ramp that continues after LAND, drifts at least 10 m horizontally. This
   is C2g on a real autopilot.

## The challenge (published with the results)

If V14d holds, `CHALLENGE.md` gains a track.

**Claim under challenge:** in configuration C2, with an independent root and adversarial noise, no
attacker drives the vehicle more than B = 31.1 m outside the 300 m fence.

**What counts as a break:** a program, in any language, speaking the harness's JSON-lines protocol,
for which `python tools/corridor_challenge.py --attacker "<program>"` prints `BREAK`. The harness,
model, check, latch and Gate must be unchanged.

**What does not count** (these are published results, not breaks):
- C1 breaches;
- the corridor;
- a common-root independent source;
- C2g;
- anything OUT OF MODEL;
- criticism of the model's realism (lag, overshoot, wind). That is welcome as a registered experiment
  and credited, but it does not break this claim.

**Also counts:** getting the harness to accept an attacker that violates S or E. That is a break of
the harness.

**If V14d is refuted:** the challenge is not published as defined. The refutation is recorded, and a
corrected bound needs a new registration.

## Limits stated before running

- **A kinematic model, not an autopilot.** Every real effect adds to the terms above: tracking lag,
  overshoot, stopping distance and wind.
- **E and S are assumptions.**
  - Nothing in a package shows that the independent source's error is within E, or that the source
    does not share a root with GNSS.
  - A faster drift that the EKF accepts without flagging scales the (k − 1)·S term.
- **One geometry:** one fence, one target, one altitude, 2-D.
- **No packages are written.** V11 already showed, on SITL, a CONSISTENT package describing a vehicle
  outside its fence. A request-time package cannot contain the flight that follows it.
- **An attacker who controls both sources beyond E is out of scope.** No comparison between two
  sources can detect it.

## Prior art (not claimed as new)

- Re-checking an authorization while its effect is under way is runtime assurance. Examples are the
  Simplex architecture (L. Sha, "Using simplicity to control complexity", *IEEE Software* 18(4):20–28,
  2001) and ASTM F3269-17, *Standard Practice for Methods to Safely Bound Flight Behavior of Unmanned
  Aircraft Systems Containing Complex Functions*.
- The request-time gap is a time-of-check to time-of-use race.
- What this registration adds is the bound for this Gate's own cross-check and latch, stated so that it
  can be broken, together with its two published failure conditions.
