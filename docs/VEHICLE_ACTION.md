# The Gate commands a simulated drone — registration and results

Status: **Registered** (2026-09-26), before any code below was written. Results are appended under
the registration and never edited into it.

Why: the author asked whether sovereign-veritas "works on" drones, defense automation and space.
It did not: before this, the only real integration was a phone model writing a note
(docs/MODEL_ACTION.md). This is the first step for vehicles, and it is a simulation.

**What this is and is not.** The Gate decides whether a flight command (take off, go to a point,
land, return home) may be sent to an ArduPilot autopilot, from a geofence, navigation health and
battery state, and records a package anyone can re-check. It is a permission layer for a vehicle's
own movement. It is not a weapon, targeting, payload or electronic-warfare function, and none will
be added here. It is not the vehicle's safety system either: ArduPilot's own failsafes act
whether or not the Gate exists.

## The design

`tools/vehicle_action.py`, one request per run:

1. **The request is the artifact**: `{"schema": "sv.vehicle_request/0", "action", "params",
   "fence": {center, radius_m, max_alt_m}, "limits": {min_fix_type, min_sats, min_battery_pct}}`.
   Whoever runs the tool writes it; later a model could propose it, as in MODEL_ACTION.
2. **A telemetry snapshot** is read from the vehicle before deciding: GPS fix type and satellites,
   EKF status flags, battery remaining, position, relative altitude, armed state, mode. Its sha256
   goes into the decision record, so the snapshot is bound to the decision.
3. **A deterministic check** of request against snapshot. Movement commands (`takeoff`, `goto`)
   PASS only if the target is inside the fence and below the ceiling, the vehicle is inside the
   fence, the GPS fix and satellite count meet the limits, the EKF reports an absolute horizontal
   position and no GPS glitch, and the battery meets its limit (unknown battery fails).
   **Recovery commands are checked differently**: `land` needs nothing from navigation, and `rtl`
   needs navigation but not the fence or battery. A fail-closed gate that refused LAND because GPS
   was lost would make the vehicle less safe; this is stated as a design rule, not discovered later.
4. **The Gate** decides from the check (verification), the capability `vehicle_command`
   (authorized by the operator), the policy `allow_only: ["takeoff", "goto", "land", "rtl"]`, the
   requested action and the runtime state. The Gate itself is unchanged (sv.gate/0).
5. **Only on ALLOW** are MAVLink commands sent; the tool then waits for the outcome (altitude
   reached, within 3 m of the target, disarmed on the ground) and records the commands sent and a
   second snapshot.
6. `tools/verify_package.py` recomputes the check from the recorded request and snapshot
   (`measurement_recomputed`), and a new check, `vehicle_check_bound`, ties the record to it: the
   recorded verification is the check's verdict, the requested action and parameters are the
   request's, and commands were sent exactly when the action ran under ALLOW.

Backends: `mavlink` (any MAVLink autopilot; here ArduCopter SITL) and `fake`, a canned stand-in
that is **not a vehicle**, for tests without a simulator. Every package names its backend.

Stated limit, the same as for the model's reply: the snapshot is recorded data. A package cannot
show the snapshot came from a vehicle; a signature shows who packaged it. In sv.gate/0 there is no
runtime field for navigation, so lost navigation reads as a REFUSE of the request (the check
fails), not a DEFER; a `nav_status` runtime field is a candidate for sv.gate/1 (issue #4).

## Registered predictions

ArduCopter SITL (built from ArduPilot master here), home 35.3632, -96.9270, fence radius 300 m,
ceiling 120 m, limits fix >= 3, satellites >= 6, battery >= 30 %:

- **V1** `takeoff` to 10 m, healthy: ALLOW; the vehicle reaches at least 9 m.
- **V2** `goto` 100 m north at 20 m, inside the fence: ALLOW; the vehicle ends within 3 m of it.
- **V3** `goto` 600 m north (outside the fence): REFUSE `verification_not_passed`; no command sent;
  the vehicle moves less than 2 m while the tool runs.
- **V4** `goto` inside the fence at 150 m (above the ceiling): REFUSE; no command sent.
- **V5** `disarm` requested in flight: REFUSE `action_not_permitted_by_policy`; no command sent.
- **V6** GPS switched off in the simulator (`SIM_GPS1_ENABLE=0`), then `goto` inside the fence:
  REFUSE `verification_not_passed`, the check naming navigation; no command sent by the tool.
  Whatever ArduPilot's own failsafe does is recorded, not claimed.
- **V7** Same GPS loss, then `land`: ALLOW; the vehicle lands and disarms. (Recovery is not gated
  on navigation.)
- **V8** Every package verifies; a resealed package with the snapshot's fix type raised fails
  `measurement_recomputed`; one whose record says commands were sent under REFUSE fails
  `vehicle_check_bound`.
- **V9** The new guard is load-bearing (`tools/verifier_mutants.py` kills it); vacuity_lint clean.

Contested navigation, where the honest expectation is partial:

- **V10** A sudden GPS position jump of about 111 m (`SIM_GPS1_GLTCH_X=0.001`) while hovering:
  ArduPilot's EKF flags a GPS glitch, and a `goto` requested during it is REFUSED. Uncertain: the
  EKF may reject the jump without setting the flag the check reads.
- **V11 (registered, not run):** a slow position drift, small enough per step that the EKF accepts
  it, passes every check here: fix type, satellite count and EKF flags stay healthy while the
  vehicle's believed position is wrong. If so, this gate does not detect spoofing that keeps the
  receiver's quality good, and no claim about GNSS-contested operation should be made from it.

Not in scope and not claimed: real hardware, a real radio link, the phone running the simulator,
defense or space use.

## Results — ArduCopter SITL (container x86_64, Python 3.11.15)

ArduPilot master built here (`./waf copter`, SITL board), run as `arducopter --model quad
--speedup 5 --home 35.3632,-96.9270,300,0` with ArduPilot's default copter parameters. Faults
injected with `tools/mav_param.py`, never by the tool under test. `--thermal-status normal`
(declared): the container has no thermal zones. The ten packages are in `runs/vehicle_sitl/`,
unsigned; each verifies `VERDICT  CONSISTENT` here.

**Unplanned, first:** the first two requests went in 45 s after start, before the simulated GPS
had a fix. Both were refused, and the check says why:

```
== --action takeoff --alt 10
before  fix 0 sats 0 ekf 1024 battery 100% alt 0.0 m armed False mode STABILIZE
check   FAIL (vehicle 10635165.4 m from fence centre > 300.0 m; gps fix 0 < 3; satellites 0 < 6; ekf has no absolute horizontal position (flags 1024))
decision REFUSE ['verification_not_passed']
sent    nothing
== --action goto --north 100 --alt 20
before  fix 6 sats 10 ekf 167 battery 100% alt 0.0 m armed False mode STABILIZE
check   FAIL (ekf has no absolute horizontal position (flags 167))
decision REFUSE ['verification_not_passed']
sent    nothing
```

(With no fix the reported position is 0, 0, which is 10,635 km from the fence. In the second, the
GPS had a fix but the EKF had not yet accepted it.) Then, after waiting for the EKF
(`ready after 0 s, ekf flags 831`):

```
== --action takeoff --alt 10
before  fix 6 sats 10 ekf 831 battery 100% alt 0.0 m armed False mode STABILIZE
check   PASS (all takeoff rules hold)
decision ALLOW []
sent    ['SET_MODE GUIDED', 'ARM', 'NAV_TAKEOFF 10.0']
after   reached True  alt 10.0 m moved 0.0 m armed True mode GUIDED
== --action goto --north 100 --alt 20
before  fix 6 sats 10 ekf 831 battery 96% alt 10.0 m armed True mode GUIDED
check   PASS (all goto rules hold)
decision ALLOW []
sent    ['SET_MODE GUIDED', 'SET_POSITION_TARGET_GLOBAL_INT 353640993 -969270000 20.0']
after   reached True  alt 20.0 m moved 100.2 m armed True mode GUIDED
== --action goto --north 600 --alt 20
before  fix 6 sats 10 ekf 831 battery 85% alt 20.0 m armed True mode GUIDED
check   FAIL (target 600.0 m from fence centre > 300.0 m)
decision REFUSE ['verification_not_passed']
sent    nothing
after   reached None  alt 20.0 m moved 0.0 m armed True mode GUIDED
== --action goto --north 50 --alt 150
before  fix 6 sats 10 ekf 831 battery 84% alt 20.0 m armed True mode GUIDED
check   FAIL (altitude 150.0 not within 2..120.0 m)
decision REFUSE ['verification_not_passed']
sent    nothing
after   reached None  alt 20.0 m moved 0.0 m armed True mode GUIDED
== --action disarm
before  fix 6 sats 10 ekf 831 battery 82% alt 20.0 m armed True mode GUIDED
check   PASS (all disarm rules hold)
decision REFUSE ['action_not_permitted_by_policy']
sent    nothing
after   reached None  alt 20.0 m moved 0.0 m armed True mode GUIDED
SIM_GPS1_GLTCH_X = 0.001
== --action goto --north 50 --alt 20
before  fix 6 sats 10 ekf 33599 battery 71% alt 20.0 m armed True mode GUIDED
check   FAIL (ekf reports a gps glitch (flags 33599))
decision REFUSE ['verification_not_passed']
sent    nothing
after   reached None  alt 20.0 m moved 24.2 m armed True mode GUIDED
SIM_GPS1_GLTCH_X = 0
SIM_GPS1_ENABLE = 0
== --action goto --north 50 --alt 20
before  fix 1 sats 3 ekf 167 battery 42% alt 5.9 m armed True mode LAND
check   FAIL (gps fix 1 < 3; satellites 3 < 6; ekf has no absolute horizontal position (flags 167))
decision REFUSE ['verification_not_passed']
sent    nothing
after   reached None  alt 4.6 m moved 0.0 m armed True mode LAND
== --action land
before  fix 1 sats 3 ekf 167 battery 41% alt 2.6 m armed True mode LAND
check   PASS (all land rules hold)
decision ALLOW []
sent    ['SET_MODE LAND']
after   reached True  alt 0.0 m moved 0.0 m armed False mode LAND
```

- **V1 confirmed.** ALLOW; 10.0 m reached.
- **V2 confirmed.** ALLOW; arrived (within 3 m and 1.5 m of altitude), 100.2 m from where it started.
- **V3 confirmed.** REFUSE; nothing sent; moved 0.0 m.
- **V4 confirmed.** REFUSE on the ceiling; nothing sent.
- **V5 confirmed.** The check passes (disarm has no vehicle-state rule) and the policy refuses it:
  `action_not_permitted_by_policy`, nothing sent. The rule that decided is the one being tested.
- **V10 confirmed**, where the outcome was uncertain: after a 0.001° (about 111 m) jump the EKF
  set its GPS-glitch flag (33599 = 32768 + 831) and the goto was refused. **The vehicle moved
  24.2 m anyway with nothing sent**: that was the autopilot responding to the glitch by itself. "Refused"
  means the Gate sent nothing; it does not mean the vehicle stayed put.
- **V6 confirmed, and the autopilot got there first.** Five seconds after the GPS was switched off
  the vehicle was already in LAND at 5.9 m: ArduPilot's own failsafe had started landing it. The
  goto was refused with the navigation failures named.
- **V7 confirmed, with a caveat.** LAND was allowed with navigation lost and the vehicle landed and
  disarmed. It was already landing on its own, so this shows that land is not refused for lost
  navigation, not that the Gate's command landed it.
- Battery fell from 100 % to 41 % across the session (simulated, at 5x speed); it stayed above the
  30 % limit for every movement request.

### V8, V9 and the tests

`tests/test_vehicle_action.py`, `fake` backend (not a vehicle), 23 tests: the decisions above plus
battery low (goto refused, land allowed), vehicle outside the fence (goto refused, RTL allowed),
RTL with GPS off (refused), the fence edge (299 m passes, 301 m fails), unknown battery (fails),
the verifier's re-implemented check agreeing with the tool's over 35 request/snapshot pairs, and
the attacker cases.

- **V8 confirmed.** Resealed: snapshot fix type raised fails `measurement_recomputed`; a command
  recorded under REFUSE, a REFUSE flipped to ALLOW, the requested action changed, and the outcome
  dropped from a run action each fail `vehicle_check_bound`. Stated limit, pinned as a test: a
  consistent rewrite of the snapshot, its hash, the check and the decision verifies unsigned.
- **V9 confirmed.**

```
307 passed
vehicle_check_bound                KILLED    tests/test_vehicle_action.py::test_v8_commands_recorded_under_refuse_fail_the_binding
VERDICT  25 of 25 KILLED, 0 SURVIVED  (396 s)
no vacuous verification found
```

### What this does and does not show

It shows the Gate governing a real autopilot's flight code (ArduPilot, in simulation): commands go
out only under ALLOW, geofence, ceiling, navigation and battery rules refuse what they should, recovery
is not blocked by lost navigation, and every decision can be re-checked from its package.

It does not show: real hardware or a real radio link; anything about latency (one command per
process, seconds each); anything under GNSS spoofing that keeps the receiver healthy (V11, still
unrun, predicts the gate cannot see it); anything about defense or space use. The navigation rules
read what the autopilot reports about itself, so they are only as good as the autopilot's estimator.

Still open: V11; the same runs on the phone (ArduPilot SITL under Termux, or the phone as a companion
computer to a real flight controller); a model proposing the request instead of an operator; a
`nav_status` runtime field so that lost navigation DEFERs instead of REFUSEs (sv.gate/1, issue #4).

## Amendment before running V11 (2026-09-26, nothing run yet)

Procedure: fresh SITL, wait for the EKF, `takeoff` to 20 m at the fence centre. Then raise
`SIM_GPS1_GLTCH_X` (the GPS reports the vehicle this many degrees further north than it is) from 0
to 0.001 (about 111 m) in steps of 0.00001 (about 1.1 m), one step per second, below ArduPilot's
default glitch radius (`EK3_GLITCH_RAD` 25 m) per step. Then request `goto` 250 m **south** at 20 m,
inside the 300 m fence as the vehicle believes it. The true position is read from SITL's own
`SIMSTATE` message, which the tool never sees.

- **V11a** Through the ramp, no snapshot shows the EKF glitch flag.
- **V11b** The goto is ALLOWed; the check passes on every rule.
- **V11c** The vehicle "arrives" by its own telemetry, while its true position ends more than 300 m
  from the fence centre, outside the fence. The package verifies CONSISTENT.

If V11b holds, the finding is that this gate, and any gate that reads the autopilot's own
estimate, cannot enforce a geofence against a spoofer who moves slowly.

## V11 results (ArduCopter SITL, container)

`tools/sitl_drift_probe.py` ramps the offset and reads SITL's true position (`SIMSTATE`); the tool
under test never sees it. Packages in `runs/vehicle_sitl_v11/`, each `VERDICT  CONSISTENT`.

**Attempt 1, confounded, kept.** The ramp went as registered, but the simulated battery drained
to 0 % during it (the default 3300 mAh at 5x speed), and the goto was refused for that:

```
before  fix 6 sats 10 ekf 831 battery 0% alt 20.0 m armed True mode GUIDED
check   FAIL (battery 0 % < 30 %)
decision REFUSE ['verification_not_passed']
```

A correct refusal that answers a different question, the same trap as MODEL_ACTION's run 1.
**Deviation for attempt 2:** `BATT_CAPACITY` set to 30000 before take-off, so the battery rule
could not decide. Nothing else changed.

**Attempt 2:**

```
start: true 0.0 m from fence centre, believed 0.0 m, true-vs-believed 0.0 m, ekf 831
step 25 (offset 0.00025 deg): true 27.8 m from fence centre, believed 0.0 m, true-vs-believed 27.8 m, ekf 831
step 50 (offset 0.00050 deg): true 55.7 m from fence centre, believed 0.1 m, true-vs-believed 55.6 m, ekf 831
step 75 (offset 0.00075 deg): true 83.5 m from fence centre, believed 0.1 m, true-vs-believed 83.4 m, ekf 831
step 100 (offset 0.00100 deg): true 111.3 m from fence centre, believed 0.1 m, true-vs-believed 111.2 m, ekf 831
ekf glitch flag seen at 0 of 100 steps
after ramp +5 s: true 111.2 m from fence centre, believed 0.0 m, true-vs-believed 111.2 m, ekf 831
== --action goto --north -250 --alt 20
before  fix 6 sats 10 ekf 831 battery 85% alt 20.0 m armed True mode GUIDED
check   PASS (all goto rules hold)
decision ALLOW []
sent    ['SET_MODE GUIDED', 'SET_POSITION_TARGET_GLOBAL_INT 353609517 -969270000 20.0']
after   reached True  alt 20.0 m moved 250.7 m armed True mode GUIDED
VERDICT  CONSISTENT  freshness=NOT_PROVEN  authenticity=NOT_PROVEN
after goto: true 361.2 m from fence centre, believed 250.0 m, true-vs-believed 111.2 m, ekf 831
```

- **V11a confirmed.** The glitch flag never set (0 of 100 steps). While hovering "in place" the
  vehicle physically flew 111 m north, holding a position that only existed in its estimate.
- **V11b confirmed.** Fix 6, 10 satellites, EKF flags 831, battery 85 %: every rule passed; ALLOW.
- **V11c confirmed.** The vehicle reported arriving 250 m south; it was truly **361.2 m** from the
  fence centre, 61 m outside a 300 m fence. The package is CONSISTENT, and every word in it is what
  the autopilot reported.

**What this means.** This Gate, and any gate or geofence that reads the autopilot's own position
estimate (ArduPilot's built-in fence included), cannot enforce a boundary against a GNSS spoofer
who moves slowly. A consistent, verifiable package can describe a vehicle that is somewhere else.
Nothing in this repository should be read as working in GNSS-contested conditions.

What would be needed, none of it built: a position source the spoofer does not control
(visual or radio navigation, map matching), a cross-check between it and GNSS with a registered
disagreement threshold, and that disagreement as a runtime input the Gate can DEFER on (the
`nav_status` field proposed for sv.gate/1). **V12 (registered, not run):** with an independent
position source in SITL (e.g. ArduPilot's simulated visual odometry) and a 25 m disagreement rule
in the check, the same ramp is refused before the goto, somewhere between steps 20 and 30.

## Amendment before building V12 (2026-09-26, nothing built yet)

**Deviation from V12 as registered:** the independent position source is not ArduPilot's simulated
visual odometry. It is a stand-in: SITL's true position (`SIMSTATE`) plus Gaussian noise, σ = 3 m
per axis, recorded in the package as `sitl-truth+noise(sigma=3m)`, **not a sensor**. It stands in
for anything the GNSS spoofer does not control (visual or radio navigation, a ground tracker).
Real sources have their own failure modes, and some can be spoofed too; this tests the Gate's rule,
not a sensor.

Design: the request may carry `limits.max_nav_disagreement_m`. When it does, the snapshot must hold
an independent position (`xpos_lat_e7`, `xpos_lon_e7`), and every rule that needs navigation
(`takeoff`, `goto`, `rtl`) fails if the autopilot's position and the independent one are further
apart than the limit, or if the independent position is missing. `land` stays ungated. Requests
without the limit behave exactly as before (V1-V11 unchanged).

- **V12a (anti-vacuity)** No spoof, limit 25 m: a `goto` inside the fence is ALLOWed; the recorded
  disagreement is under 10 m.
- **V12b** The V11 ramp (0.001°, 100 steps), then the same `goto` 250 m south: REFUSED, the check
  naming the disagreement; nothing sent.
- **V12c** Running the check on a snapshot at every step of the ramp, it first fails between steps
  20 and 30.
- **V12d** Under the spoof, `rtl` is REFUSED (it navigates by the spoofed position) and `land` is
  ALLOWed.
- **V12e** Without the limit in the request, the same spoofed goto is ALLOWed, as in V11: the rule,
  not something else, is what refuses in V12b.

## V12 results (ArduCopter SITL, container)

Fresh SITL, `BATT_CAPACITY` 30000 as in V11 attempt 2. Requests with `--max-disagreement 25
--xpos-sigma 3` carry the cross-check; the independent position is the stand-in named in every
snapshot, `sitl-truth+noise(sigma=3m)`. Packages in `runs/vehicle_sitl_v12/`, each `VERDICT
CONSISTENT`. Recorded disagreement per package (autopilot position vs independent position):

```
takeoff  limit 25.0  gap 4.4    ALLOW
goto     limit 25.0  gap 8.6    ALLOW     (V12a, 50 m north, before the spoof)
goto     limit 25.0  gap 110.2  REFUSE    (V12b, after the ramp)
rtl      limit 25.0  gap 115.2  REFUSE    (V12d)
goto     no limit    -          ALLOW     (V12e)
land     limit 25.0  gap 108.7  ALLOW     (V12d)
```

The ramp, with the vehicle check run on a fresh snapshot at every step (`tools/sitl_drift_probe.py
ramp-check`):

```
step   0: PASS  all goto rules hold
step  10: PASS  all goto rules hold
first FAIL at step 18 (offset 0.00018 deg): autopilot and independent position disagree by 28.0 m > 25.0 m
step  20: PASS  all goto rules hold
step  30: FAIL  autopilot and independent position disagree by 34.5 m > 25.0 m
...
step 100: FAIL  autopilot and independent position disagree by 108.4 m > 25.0 m
first failing step: 18
```

Then the spoofed requests:

```
== --action goto --north -250 --alt 20 --max-disagreement 25 --xpos-sigma 3
check   FAIL (autopilot and independent position disagree by 110.2 m > 25.0 m)
decision REFUSE ['verification_not_passed']
sent    nothing
== --action rtl --max-disagreement 25 --xpos-sigma 3
check   FAIL (autopilot and independent position disagree by 115.2 m > 25.0 m)
decision REFUSE ['verification_not_passed']
== --action goto --north -250 --alt 20
check   PASS (all goto rules hold)
decision ALLOW []
after   reached True  alt 20.0 m moved 300.7 m armed True mode GUIDED
after unguarded goto: true 361.2 m from fence centre, believed 250.0 m, true-vs-believed 111.2 m, ekf 831
== --action land --max-disagreement 25 --xpos-sigma 3
check   PASS (all land rules hold)
decision ALLOW []
after   reached True  alt 0.0 m moved 0.0 m armed False mode LAND
```

- **V12a confirmed.** Before the spoof: 4.4 m and 8.6 m, both under 10 m; both ALLOWed.
- **V12b confirmed.** After the ramp the same goto that V11 allowed is REFUSED, the check naming a
  110.2 m disagreement; nothing sent.
- **V12c refuted, and the way it failed matters.** The check first failed at step 18, not between
  20 and 30, and at step 20 it **passed again**. With σ = 3 m of noise on each axis, a disagreement
  near 25 m crosses the limit and back from one reading to the next. A single-reading rule flaps at
  its threshold; which request gets refused near the edge is partly chance. The prediction ignored
  the noise it was built on.
- **V12d confirmed.** Under the spoof RTL is REFUSED (it would navigate by the spoofed position);
  LAND is ALLOWed.
- **V12e confirmed.** Without the limit in the request the same goto is ALLOWed and the vehicle ends
  361.2 m from the centre, 61 m outside the fence, exactly as in V11. The rule is what refused in
  V12b.

What this shows: given a position source the spoofer does not control, a registered disagreement
limit turns V11's silent breach into a refusal, and the package records both positions so anyone
can re-check it. What it does not show: that any real sensor is that source (the stand-in is SITL's
truth plus noise; a real one has its own errors and may itself be spoofable), or anything about a
spoofer who drifts the independent source too.

**V13 (registered before its run; result below):** requiring the disagreement to exceed the limit on 3 consecutive
readings before refusing (and to fall below 80 % of it on 3 before allowing again) removes the
flapping: over the same ramp, one transition from PASS to FAIL and none back.

## V13 results (ArduCopter SITL, container, 2026-09-27)

Fresh SITL, `BATT_CAPACITY` 30000, `takeoff` to 20 m with `--max-disagreement 25 --xpos-sigma 3`
(package `runs/vehicle_sitl_v13/sv_package_a911244dfcf7.json`, `VERDICT CONSISTENT`). Then
`python tools/sitl_drift_probe.py ramp-check-v13`: the V11 ramp, running the single-reading check and
the V13 latch (`DisagreementLatch(25.0)`: 3 readings over the limit to latch, 3 under 20.0 m to
release) side by side on the same readings. Full output in `runs/vehicle_sitl_v13/ramp_check_v13.txt`.

```
step  20: gap   24.3 m  single-reading PASS  latched PASS
first FAIL at step 22 (offset 0.00022 deg): autopilot and independent position disagree by 27.3 m > 25.0 m
step  25: gap   24.8 m  single-reading PASS  latched FAIL
step  30: gap   32.1 m  single-reading FAIL  latched FAIL
first failing step: 22
single-reading rule: PASS->FAIL 3, FAIL->PASS 2
V13 latch (3 over / 3 under 80%): PASS->FAIL 1, FAIL->PASS 0
```

- **V13 confirmed.** Over the ramp the latch made one transition from PASS to FAIL and none back.
  On the same readings the single-reading rule flapped: 3 transitions to FAIL, 2 back to PASS
  (step 25 read 24.8 m, just under the limit, and passed).
- **Cost, stated:** the latch refuses no earlier than the third reading over the limit, so it adds
  up to two readings of delay (here, one per second) against the single-reading rule.
- **Limit:** one run, one ramp rate, one noise level. It shows the latch removes flapping at this
  threshold. It does not show the right `k` or release fraction for a real sensor.

## V14 (registered 2026-10-02, before any code for it)

The cross-check above runs once, when a command is requested; nothing re-checks during the flight. V14
asks how far a GNSS spoofer can drive the vehicle after the ALLOW, what bound the same cross-check gives
if it runs on every reading, and what that bound rests on. Registered in `docs/V14_CORRIDOR_PREREG.md`;
results will go in `docs/V14_CORRIDOR_RESULTS.md`.

**V14 result (2026-10-02):** 8 of 8 as registered, in a kinematic model, not on SITL
(`docs/V14_CORRIDOR_RESULTS.md`). After the ALLOW, today's request-time check bounds nothing. The same
check re-run on every reading bounds the breach at about 31 m, given an independent source and a LAND
that does not navigate by GNSS.

## V15 (registered 2026-10-02, before any code for it)

When A (GNSS) is untrustworthy, can a recovery decision stay admissible if the second source B is
unavailable, stale, replayed or derived from A? The question comes from Amos Tipton's A/B Recovery
Challenge. V15 is software decisions on constructed inputs, with no physical claim. Registered in
`docs/V15_RECOVERY_PREREG.md`.

**V15 result (2026-10-02):** 8 of 8 as registered, on constructed inputs with no vehicle
(`docs/V15_RECOVERY_RESULTS.md`). One correction: V15b's stated count was wrong (7, not 5). Today's
Gate allows `land` on the same snapshot that refuses `goto`. It accepts any second source that agrees
with A: stale, replayed or derived. A Gate nonce stops stale and replayed sources; nothing tested
stops a derived one.
