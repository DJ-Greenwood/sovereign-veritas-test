# Attack harness: false approvals per attack class (registered 2026-09-27, before the run)

**Question.** An attacker holds the committed vehicle evidence packages but not the author's signing
key, and cannot write to the author's witness log. Which attacks get a package *accepted* by
`tools/verify_package.py`, and under which defender configuration?

**Tool.** `tools/attack_harness.py`. Deterministic, stdlib plus `ssh-keygen`. It builds a
throwaway "author" key and a throwaway "attacker" key in a temporary directory (never the phone's
`~/.ssh/sv_package_ed25519`), signs every genuine package with the author key, and witnesses them
in time order (the timestamp of each package's last chain record), so the last one is the latest.

**Corpus.** The 21 committed ArduCopter SITL packages: `runs/vehicle_sitl/` (10),
`runs/vehicle_sitl_v11/*/` (4), `runs/vehicle_sitl_v12/` (6), `runs/vehicle_sitl_v13/` (1).

**Defenders.** Accept means every check passes.

| | checks |
|---|---|
| D0 | `verify()` only: internal consistency, recomputation, gate replay |
| D1 | D0 + detached signature against the author's allowed_signers |
| D2 | D1 + the author's witness log (`--witness-log`) |

**Attack classes.** The attacker is given the best move available: every digest, the check, the
chain record and the decision are recomputed with the verifier's own functions ("reseal"). For D1
and D2 the attacker tries both the source package's genuine signature and a signature with their
own key; an attempt counts as accepted if either passes.

| id | attack | applied to |
|---|---|---|
| A1 | flip the decision (REFUSE↔ALLOW), no reseal | all 21 |
| A2 | flip the decision, reseal | all 21 |
| A3 | rewrite the observation: healthy telemetry (fix 6, 10 sats, EKF 831, battery 100 %, independent position = autopilot position), recompute check and decision, reseal | the 9 packages refused by `verification_not_passed` |
| A4 | splice real observation: the `telemetry_before` of a genuine PASS package, recomputed as A3 | the same 9 |
| A5 | swap the request: move an allowed goto's target 100 m east, recompute, reseal | the 4 ALLOWed gotos |
| A6 | stale: an older genuine package with its genuine signature | the 20 non-latest |
| A7 | replay: the latest genuine package again, with its signature | 1 |

## Predictions

- **P0 (anti-vacuity: the harness can report acceptance).** Genuine packages: D0 21/21, D1 21/21,
  D2 1/21 (the latest only).
- **P1** A1: 0 accepted under D0, D1 and D2.
- **P2** A2: 0 accepted under D0 (the gate replay and the chain record still disagree with a
  flipped decision).
- **P3** A3: D0 accepts at least one (known limit K3: only a signature binds the observation);
  D1 0/9, D2 0/9.
- **P4** A4: as P3.
- **P5** A5: D0 accepts at least one (a consistent rewrite of the request); D1 0/4, D2 0/4.
- **P6** A6: D0 20/20, D1 20/20 (freshness NOT_PROVEN without a witness), D2 0/20.
- **P7 (a registered gap, not a pass)** A7: accepted under D0, D1 and D2. The witness proves
  "newest", not "used once"; stopping a replay is the consumer's job (a nonce, or refusing a
  digest it has already acted on).

**Unrun, left open (P8).** An attacker who can also write the witness log (a force-push to an
unprotected branch) defeats D2 for A6. Not tested here: it needs a second git remote.
