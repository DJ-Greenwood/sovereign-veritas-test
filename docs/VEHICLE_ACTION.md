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
