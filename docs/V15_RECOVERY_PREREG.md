# V15 — Recovery admissibility when the second source is missing, stale or not independent: registration

Status: **Registered** (2026-10-02), before any code for it was written. The harness
(`tools/recovery_admissibility.py`) is built after this registration is merged. Results will go in
`docs/V15_RECOVERY_RESULTS.md`; this file is not edited after the run.

## Provenance

- **The question** comes from Amos Tipton's **A/B Recovery Challenge**. He raised it in a public
  discussion of the V14 challenge track, after V14 was published. It is a question, not code, and his
  attribution does not imply that he endorses anything here.
- **The case matrix** (seven cases) and the wording of the distinction in the next section were
  specified by the author, Chad Holland, in session.
- **The design** of the experiment, the policies P1 and P2, the admissibility table and the predictions
  are Claude (Opus 5.5)'s.
- **This is not a continuation of the "Dependent Evidence" proposal.** That proposal's provenance is
  INDETERMINATE (`docs/LINEAGE.md`).

## Scope, stated first

V15 tests **software decision behaviour under constructed inputs**. Each input is a request and a
telemetry snapshot built by hand.

It makes **no claim** about:
- physical vehicle safety;
- real navigation performance;
- what any real GNSS spoofer can do.

V14's 59.95 m was **model-derived**: a kinematic model in which LAND holds position on the spoofed
estimate. It was not observed on any vehicle. V15 does not cite it as a demonstration and does not
rely on it.

## The question

> When the primary source A (the autopilot's GNSS-based position) becomes untrustworthy, can a
> recovery decision remain admissible when the proposed independent source B is unavailable, stale,
> replayed, or derived from A?

**The distinction under test** (Amos Tipton's point): evidence sufficient to **invalidate** an earlier
approval is not automatically evidence sufficient to **authorize** the recovery action.

## What is under test

### P0 — the real code
- The Gate, through `EvidenceWorkflow`.
- `vehicle_check` from `tools/vehicle_action.py`, unchanged.
- Requests carry `max_nav_disagreement_m = 25`, which is the V12 configuration.
- Each request is decided from one snapshot.
- P0 has no field for when B was observed, where B came from, or any earlier decision.

### P1 — declared metadata (written for V15)
P1 is P0 plus rules on fields that **the snapshot writer declares**:
- `xpos_observed_at`, which must be within 2 s of the decision time;
- `xpos_root`, which must not be `gnss` or derived from it.

### P2 — established freshness (written for V15)
P2 is P0 plus an authenticated B message:
- **The key:** B's message carries a MAC under a key held by B and the Gate, and **not by whoever
  writes the snapshot**.
- **The nonce:** for each decision, the Gate issues a fresh nonce, and the message must echo it.
- **The sequence number:** it must exceed the last one the Gate accepted.

P2 does **not** read P1's declared labels. In case 4, B's own device does not know that its value
derives from A, so the device cannot honestly attest to independence.

In this harness the MAC is HMAC-SHA256 with a test key. That simulates a trust arrangement; it does
not show that such an arrangement exists on any vehicle.

### Recovery actions
- **`rtl`** navigates home on A, as ArduCopter's RTL does.
- **`land_hold`** is the `land` that P0 can request today. Its executed meaning is ArduCopter's LAND,
  which, according to ArduCopter's documentation, holds horizontal position on GNSS while it has a lock.
  V15 does not demonstrate that.
- **`land_nohold`** is a descent that uses no horizontal position source. P0's request schema
  **cannot express it**. P1 and P2 can.
- **`goto`** is the original movement, included to test the invalidation side.

## Constructed cases

All cases share the same world:
- The decision is taken at t1 = 1000 s.
- The vehicle is truly hovering 100 m north of the fence centre.
- A "compromised" means A reports the vehicle 60 m south of where it is.
- A "healthy" means A has an error of 1 m.
- B "fresh" means B is the true position plus a 2 m error, observed at t1 − 0.5 s.

| # | A | B | B as constructed |
|---|---|---|---|
| 0 | healthy | fresh | positive control |
| 1 | compromised | unavailable | no `xpos` fields |
| 2 | compromised | fresh | true position + 2 m |
| 3 | compromised | stale | observed at t1 − 30 s, when the vehicle was 40 m north, which agrees with the spoofed A |
| 4 | compromised | fresh-looking, derived from A | A's reading + 2 m, observed now |
| 5 | compromised | replay of a prior B | B's message from t1 − 30 s (vehicle 40 m north), byte for byte |
| 6 | healthy | unavailable | control |
| 7 | healthy | stale | observed at t1 − 30 s at 40 m north; the vehicle has since moved 60 m |

Cases 3, 4 and 5 also run in a **forged** variant. In each, the snapshot writer, who does not hold P2's
key, changes the labels:
- 3f and 5f declare `xpos_observed_at = t1`;
- 4f declares `xpos_root = "independent"`.

In 5f, the forger also re-sends the old MAC.

## Admissibility table (normative, registered before running)

This table is a **proposal** for what a correct recovery decision is. It is not a fact, and it is
recorded so that each policy can be scored against it.

**The rule:** an ALLOW is justified only if the action depends on no position source that the
available evidence fails to establish as trustworthy. A REFUSE is justified otherwise.

**Applying the rule:**
- `land_nohold` depends on no horizontal position source. Its ALLOW is justified in every case.
- `rtl`, `land_hold` and `goto` all navigate on A.
  - Their ALLOW is justified **only in case 0**: there, a fresh, authentic and independent B
    corroborates A.
  - In cases 6 and 7, REFUSE is justified even though A happens to be healthy, because nothing
    establishes that it is. That refusal is a cost, and V15 measures it as one (V15h).

## Registered predictions

- **V15a — P0, `rtl`.**
  - P0 ALLOWs in cases 0, 3, 4 and 5.
  - P0 REFUSEs in cases 1, 2, 6 and 7.
  - Cases 3, 4 and 5 are **3 unjustified ALLOWs**: a stale, derived or replayed B that agrees with the
    spoof passes the cross-check.
  - Case 7 is refused for disagreement (the stale B is 60 m off), not for staleness. P0 has no
    staleness concept.
  - The forged variants decide exactly as the honest ones, because P0 reads no labels.
- **V15b — P0, `land` (land_hold).** P0 ALLOWs in **all 8 cases**, because `land` has no vehicle-state
  rule. That makes 5 unjustified ALLOWs (cases 1–5) if LAND holds on GNSS. P0 has no request that means
  `land_nohold`.
- **V15c — invalidation is not authorization.** In case 2, a single snapshot gives:
  - `goto` REFUSE, with the reasons naming the disagreement (the invalidating evidence);
  - `land` ALLOW, on the same evidence.

  P0's decision record gives no sign that `land`'s ALLOW rested on anything beyond the absence of
  rules.
- **V15d — indistinguishability.** For every action, P0's decisions in case 1 and case 6 are equal.
  - Neither snapshot contains anything that establishes A as compromised or healthy.
  - A's reported position is not evidence of its own compromise.
- **V15e — P1, declared metadata.**
  - With **honest labels**, P1 matches the admissibility table in all 8 cases × 4 actions: 0
    unjustified ALLOWs.
  - With **forged labels**, P1 gives unjustified `rtl` ALLOWs in **3f, 4f and 5f** (3 of 3).
  - Declared freshness and declared independence are only as good as the writer.
- **V15f — P2, established freshness.**
  - P2 REFUSEs `rtl` in 3, 3f, 5 and 5f: no valid MAC over the current nonce, or a sequence number
    that does not advance.
  - P2 **ALLOWs `rtl` in cases 4 and 4f**: B's own device honestly MACs a value derived from A.
  - A MAC, a nonce and a sequence number can establish freshness and origin under the key assumption.
    They **cannot establish independence**.
  - P2's only unjustified ALLOWs are in cases 4 and 4f; everywhere else it matches the table.
- **V15g — no link to the invalidated approval.** These are run through `tools/vehicle_action.py` with
  the `fake` backend (not a vehicle).
  - The setup is a `goto` package, then a `land` package.
  - The `land` package contains **no reference** to the earlier decision: no record id, digest or
    package hash. The count is 0.
  - Nothing in the format links a recovery to the approval it replaces. Tracing in either direction
    (decision → evidence, evidence → later decisions) is therefore unavailable across decisions.
- **V15h — the cost of being correct.** P2 REFUSEs `rtl` and `land_hold` in cases 6 and 7, where A is
  healthy, and allows only `land_nohold`. The healthy-vehicle refusal count is 4 of 4.
  - Without an established B, a correct policy grounds a healthy vehicle as readily as a spoofed one.
    This is what V15d predicts at the information level.

**V15i — registered, not run (the next step).**
1. On ArduCopter SITL, check whether LAND drifts under a GNSS offset ramp that continues after LAND,
   which would turn V15b's "if LAND holds on GNSS" into a measurement.
2. Check whether a descent that uses no horizontal position can be commanded at all through MAVLink on
   ArduCopter, and with which mode and parameters, without assuming the answer.

## Scoring and outputs

- **Every decision** (policy × case × action) is printed and written to `results/v15_recovery/`. The
  run then fails or passes on each prediction.
- **The outcome digest** is pinned after the run, as in V14.
- **The sabotage switch** (`--sabotage`) disables P2's nonce check. V15f must then fail, which shows
  that the harness can return a different outcome.

## Limits stated before running

- **The table is a proposal.** Another policy could weigh availability higher. The decisions are
  scored against the table, not against safety.
- **P1 and P2 are this project's designs.** Their agreement with the table on honest inputs (part of
  V15e, and V15f outside cases 4 and 4f) is a check of the harness, not evidence about the world. The
  informative parts are:
  - P0, which is the real code;
  - the forged variants;
  - cases 4 and 4f under P2.
- **HMAC with a test key stands in for a trust arrangement.** Key custody, key compromise and a
  compromised B device are out of scope.
- **One geometry, one spoof offset (60 m), one staleness (30 s), one limit (25 m).** The case values
  were chosen to make each mechanism visible. They are not sampled from anything real.
- **No physical claim.** In particular, V15 does not show that LAND drifts. V15b is conditional on the
  documented ArduCopter behaviour, and V15i is how to check it.
