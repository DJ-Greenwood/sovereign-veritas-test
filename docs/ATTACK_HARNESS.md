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

## Results (container x86_64, Python 3.11.15, 2026-09-27)

`python tools/attack_harness.py --json results/attack_harness/result.json`, 2.7 s. Output in
`results/attack_harness/output.txt`:

```
corpus 21 packages, latest runs/vehicle_sitl_v13/sv_package_a911244dfcf7.json
class      n      D0     D1     D2   checks that refused under D0
GENUINE   21   21/21  21/21   1/21   -
A1        21    0/21   0/21   0/21   decision_record_matches, execution_only_if_allowed, gate_replay, package_digest, vehicle_check_bound
A2        21    0/21   0/21   0/21   execution_only_if_allowed, gate_replay, vehicle_check_bound
A3         9    9/9    0/9    0/9    -
A4         9    9/9    0/9    0/9    -
A5         4    4/4    0/4    0/4    -
A6        20   20/20  20/20   0/20   -
A7         1    1/1    1/1    1/1    -
```

P0-P7 all held. What that means, class by class:

- **The consistency checks alone (D0) stop decision tampering and nothing else.** A flipped decision
  is refused 21/21 with or without a reseal. But every observation rewrite (A3 9/9, A4 9/9) and every
  request swap (A5 4/4) is accepted by D0: a resealed package is internally consistent by
  construction. D0's job is to show the decision follows from the recorded evidence, not that the
  evidence is real.
- **The signature (D1) is what stops forgery:** 0 of 34 forged packages accepted, with either the
  source's genuine signature or the attacker's own key attached.
- **The witness (D2) is what stops staleness:** 20/20 older genuine packages pass D1 and 0/20 pass
  D2.
- **Replay of the latest is not stopped by anything here (A7, 1/1 under D2),** as registered. A
  consumer must refuse a package digest it has already acted on.

**Found while running, not registered:** the A5 forgeries keep `commands_sent` as recorded
(`SET_POSITION_TARGET_GLOBAL_INT` with the *old* target), and D0 does not compare the sent command
with the request's parameters. Binding them would not change D0's A5 result against this attacker,
who can rewrite `commands_sent` in the same reseal. It would catch a careless forgery only, so it is
noted, not built.

**Limit.** 21 packages from one simulator and one attacker model (no key, no witness write access).
A stolen author key defeats D1 and D2 completely; that is the key-custody problem, out of scope.

## Round 2: malformed signatures and witness logs (registered 2026-09-27, before the code)

Three more classes. The same harness, with the flag `--round2`.

| id | attack | applied to |
|---|---|---|
| A8 | a malformed signature attached to a genuine package: an empty file, 64 random bytes, the genuine signature cut in half, and a valid author signature under the wrong namespace (`file`) | 21 packages × 4 |
| A9 | a corrupted witness log, presented with the latest package: no header, a gap in `seq`, a repeated digest, a digest that is not lowercase hex, a header and nothing else | 5 logs |
| A10 | rollback: the attacker controls the log and deletes its last line, presented with the second-latest package (this runs P8 from round 1) | 1 |

- **P9** A8: D1 accepts 0 of 84, and no attempt ends in an unhandled exception.
- **P10** A9: every corrupted log is refused as unreadable (`WitnessUnreadable`, which the CLI reports
  as COULD NOT LOOK, exit 2). None is read as a verdict, so D2 accepts 0 of 5. The empty log is the
  exception: it is well-formed with no entries, so it gives `NOT_WITNESSED`, which is also a refusal.
- **P11 (the gap, stated in advance)** A10: D2 accepts the rolled-back package, 1 of 1. The witness is
  only as good as the log's integrity. On GitHub that means a protected branch, which the harness
  cannot test.

**Unrun, left open (P12).** Anchoring the log's head digest somewhere the author does not control (a
second repository, or a public timestamp) makes A10 detectable. That is not built.
