# Break the Gate

Anyone may try. A success is credited by name in STATUS.md. A careful reproduction is credited as well.

## What counts as a break

Get `tools/verify_package.py` to print `VERDICT  CONSISTENT` **with** `--signature` / `--allowed-signers` /
`--identity` and `--witness-log` (defender D2 in `docs/ATTACK_HARNESS.md`) for a package that:

- was not signed by the key in the allowed_signers file, or
- says ALLOW where the Gate's rules (`CONTRACT.md`) on its recorded inputs say DEFER or REFUSE, or
- is older than the newest package in a witness log you did not write.

A break of `tools/consumer.py` also counts: it accepting the same package twice, or accepting a log
that does not extend one it has already seen.

## Already known: these do not count (they are published limits)

- Without a signature, any fully consistent rewrite verifies (K1-K3 in `tools/nvidia_challenge.py`;
  A3-A5 in the harness).
- Replaying the latest package against the verifier alone (A7); `tools/consumer.py` is the fix.
- Rolling back the witness log against a consumer that has never seen the newer log (A10, round 3).
- Anything that needs the signing key. Key custody is out of scope.
- The companion route check trusts the companion's own labels (`docs/COMPANION_ACTION.md`).

## Start here

    git clone https://github.com/holland202/sovereign-veritas && cd sovereign-veritas
    python -m pip install -e ".[test]"
    python -m pytest -q
    python tools/attack_harness.py --round2 --round3        # every registered prediction prints HELD
    python tools/gate_contract.py --check kernel             # digest 44823d0f...0628

Open an issue with the package, the commands and the output. A reproduction of the numbers (on any
platform) is also worth an issue: say what you ran and what it printed.
