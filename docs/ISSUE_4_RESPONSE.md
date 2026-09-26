# Response to issue #4 (Nick Kouns' review of sv.gate/0) — registration and results

Status: **Registered** (2026-09-26). Results are appended under the registration and never edited
into it. The issue: https://github.com/holland202/sovereign-veritas/issues/4

The review's scope note is accepted as written: sv.gate/0 is a good decision procedure over
records, and the break is treating it as a verifier of reality and a gate on action. This file
records, break by break, what is accepted, what is fixed now, what waits for sv.gate/1, and the
evidence from 2026-09-26 that bears on each. Acceptance path chosen: **2 now** (a written position
on every break, with limitation lines), **1 later** (sv.gate/1 with new vectors), and **3 stays
open** (a second-author implementation remains the most valuable external object).

## Fixed now (they do not touch the frozen sv.gate/0 vectors)

**B4, two predicates for one claim.** Reproduced before any change:

```
authorized=True   evidence={'ok': 'FAILED'}   check -> (True, [])
authorized=1      evidence={'ok': [0]}        check -> (True, [])
authorized='yes'  evidence={'ok': True}       check -> (True, [])
```

`CapabilityRegistry.check()` read `authorized` and each evidence flag by truthiness; the Gate reads
them by identity (`is True`). No code in this repository calls `check()`, which is how the split
survived. Registered:

- **R1** After the fix, `check()` returns False for every (authorized, evidence) pair above except
  `authorized=True` with `{'ok': True}`, and agrees with the Gate's rule on the same pairs.
- **R2** The Gate and its 4690 vectors are unchanged: the conformance digest stays
  `44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628`.

**B11, architecture file is not the kernel.** ARCHITECTURE.md gets a table at the top saying which
layers exist in this repository and which are targets.

## Positions on every break

| break | accepted? | now | sv.gate/1 |
|---|---|---|---|
| B1 PASS is an unauthenticated label | yes | stated limitation; demonstrated below | bound status, signed by an allowed verifier |
| B2 authorization is a mutable bit | yes | stated limitation | signed grant checked against allowed authorizers |
| B3 required evidence is a flag | yes | stated limitation | evidence slots that must be MEASURED or DERIVED |
| B4 two predicates | yes | **fixed** (R1, R2) | — |
| B5 parent check one hop | yes | stated limitation | walk the grant chain; cycle or gap refuses |
| B6 max_steps skipped without step_count | yes | stated limitation | missing step_count refuses |
| B7 runtime defaults healthy | yes | stated limitation (DEFAULTED already tagged) | DEFAULTED blocks ALLOW; no healthy defaults |
| B8 Python equality in allow_only | yes | pinned as a porting trap in CONTRACT.md | typed string equality |
| B9 CONSISTENT is not authentic, fresh or executed | yes | signatures and witness log exist; replay is open | consumed execution token (your R2 artifact) |
| B10 dual implementation is one author | yes | stated in CONTRACT.md | unchanged: needs a second author |
| B11 architecture is not the kernel | yes | **fixed** (table) | — |

## Evidence from 2026-09-26 that bears on the review

Each of these came from a run whose predictions were registered first; details in the linked docs.

- **B1 in practice** (docs/VEHICLE_ACTION.md, V11): a slow GPS spoof walked a simulated ArduCopter
  61 m outside its geofence while every check passed and the package verified CONSISTENT. The
  package faithfully recorded what the autopilot believed. That is B1's point with a vehicle
  attached: the Gate verified the record, not the world.
- **B1, from the hardware side** (docs/PLATFORM_TESTS.md): on the S25 the Adreno GPU's Vulkan path
  silently corrupted the model's output. The Gate refused every reply only because the garbage
  failed the check; a wrong-but-well-formed reply would have passed. The same model, file and
  prompt gave five different wrong answers to one multiplication across five compute paths.
- **B9, provenance of the model itself** (docs/MODEL_ACTION.md): the first phone run was answered
  by a stale server running a different model; the package recorded the operator's claim. Fixed by
  `model_file_named`, which is still a name check on two claims, not proof of which weights ran.
- **An unregistered break, found by an NVIDIA-hosted model** (docs/PLATFORM_TESTS.md, N1): the
  verifier ignored unknown keys, so unchecked text could ride inside a CONSISTENT package. Fixed by
  closing sv.package/0 (`schema_closed`).

## Limitation lines

Every package already carries the four sv.package/0 statements (freshness, authenticity, verifier
identity, resource state). The review asks for the B1-B7 limits to be mandatory on ALLOW packages.
Not done in sv.package/0, and why: the verifier cannot tell a new package missing the line from a
published one made before it existed, so a "mandatory" fifth line could simply be dropped and the
package would still verify. A requirement that can be deleted without detection would be a
vacuous guard. It needs a version marker: **R3 (registered, not built)** sv.package/1 carries a
fifth statement, "gate scope: ALLOW means the recorded inputs satisfy the Gate; the verification
status, authorization and evidence flags are written by the caller, not proven (issue #4)", and
its verifier refuses a /1 package without it.

## Results (container x86_64, Python 3.11.15)

- **R1 confirmed.** `tests/test_capability_predicate.py`, 4 authorizations x 6 evidence values:
  `24 passed` with the fix; `15 failed, 9 passed` with the fix removed. Only `authorized=True` with
  `{"ok": True}` passes, as in the Gate.
- **The review's trap caught its test.** The first version of that test compared
  `evidence == {"ok": True}`, which Python holds true for `{"ok": 1}`: the B8 porting trap, inside a
  test written to close B4. It failed one case against correct code, which is how it was found;
  now it compares by identity.
- **R2 confirmed.** Both implementations, after the change:
  `conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628 (expected 44823d0f…a250628)`, `VERDICT  CONFORMS`.
- **B11 done.** ARCHITECTURE.md now opens with a table of what is in this repository and what is a
  target or lives elsewhere.
- Full suite `357 passed`.

Still open from this response: sv.gate/1 (B1-B3, B5-B7, B9), R3 (sv.package/1 with the gate-scope
line), and a second-author implementation.
