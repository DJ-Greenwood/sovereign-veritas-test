# JG-2: checking section 6 of James Greenwood's report (non-repudiation and canonicalization) — registration

**Status:** REGISTERED 2026-10-03, in a commit of its own. The probe does not exist yet. This file is
not edited after this commit; results go in `docs/JG2_RESULTS.md`.

**Method:** principia-artificialis `METHOD.md` at `646eed7`. This is the next unrun test named by JG-1.

**Source:** section 6 of the report, preserved verbatim in
`docs/external/greenwood_2026-10-03_challenge-and-audit-report.md`. The report is AI-assisted (Gemini).
Its three statements are claims about this repository. Here they are checked against the code
(C-EXT), not adopted.

**Provenance:** AI participation → human validation → human editing/curation → human responsibility.
- **AI participation:** Claude (Anthropic, Opus 5.5).
- **Human review:** direction only. Chad Holland: "Proceed".
- **Responsibility:** Chad Holland.
- **Self-tested.**

## The three statements, paraphrased (the exact text is in the preserved report)

- **S1.** All evidence records use `canonical_json()` (sorted keys, compact separators,
  `ensure_ascii=False`), giving byte-level hash determinism across Linux, Android, macOS and Windows.
- **S2.** The `.gitattributes` rules prevent line-ending drift from corrupting package signatures or
  witness logs.
- **S3.** Non-repudiation is strictly enforced by detached Ed25519 signatures (`.json.sig`), bound to
  the keys in `keys/allowed_signers`.

## What was read before this registration (exploratory, C-EXPLORE)

The following was read, and partly run, before this file was written:
- `.gitattributes`;
- `evidence.canonical_json` and its single `sha256` call site;
- `package.sha256_hex` and its callers;
- the signature options of `tools/verify_package.py` and `tools/consumer.py`;
- `git check-attr` on six paths.

The predictions below rest on that reading. The checks themselves are run only by the probe.

## Predictions

| ID | Statement | Prediction |
|---|---|---|
| P1 | S1 | Every `sha256` in the `sovereign_veritas/` package hashes either `canonical_json(...)` or raw artifact bytes. For a record whose values contain non-ASCII text, the evidence digest equals `sha256(canonical_json(payload))` and does not equal the digest of `ensure_ascii=True` JSON |
| P2 | S1, "across … Android" | **NOT RUN here.** CI covers Linux, macOS and Windows; this probe runs on Linux only |
| P3 | S2 | `git check-attr text` is `unset` for `contract/gate_vectors.jsonl`, `evidence/*.json`, `evidence/*.sig`, `witness/packages.log` and `keys/allowed_signers` |
| P4 | S2, beyond its scope (ours) | `git check-attr text` is `unspecified` for `docs/external/*.md`, files whose recorded sha256 is of their exact text. They are therefore **not** protected from line-ending conversion on checkout. A gap |
| P5 | S3 | All 8 `evidence/*.json` packages verify with `ssh-keygen -Y verify` (namespace `sv-package`, identity `holland202`), and the key in `keys/allowed_signers` is `ssh-ed25519` |
| P6 | S3, anti-vacuity | A copy of a package with one byte changed fails the same check |
| P7 | S3, "strictly enforced" | **Signatures are opt-in:** `tools/consumer.py accept` on a valid package without `--signature` exits 0, and `tools/verify_package.py` without `--signature` reports authenticity `NOT_PROVEN` rather than failing. So "strictly enforced" holds only when the caller asks for the check |

## Fix (design, frozen here)

- **F1:** add `docs/external/*.md -text` to `.gitattributes`. After it, P4's paths report `unset`.
- **Not fixed here:** whether signatures should become mandatory (P7). That is a contract and format
  decision, and it is Chad Holland's. It is recorded as a proposal.

## Simplest rival

"S3 is only wording, since the repository already says that an unsigned package is NOT_PROVEN." P7
tests the behaviour itself. The rival is consistent with P7 holding: then the overstatement is in the
report, not in the code.

## Trigger table (METHOD.md §3)

| Trigger | Answer |
|---|---|
| Feasibility | No. Fixed files |
| Noise | No |
| Statistics | No |
| Evidence | **No.** These are integrity and authenticity checks of stored artifacts, not a rule's handling of fresh, stale or replayed evidence |
| Independence | No independence is claimed. Greenwood's Windows run of D1 (signature PASS) is his re-run, reported in his words |
| External | **Yes** (C-EXT): the claims are checked one by one, here |
| Device | **Yes**, for P2's "Android". It is not run here and is labelled NOT RUN |
| Verdict code | **Yes** (C-BUILD): the probe's checks fail closed. A missing `ssh-keygen` gives exit 2 (COULD NOT RUN), not a pass |
| Exploration | **Yes**: the reading listed above |
| Method comparison | No |

**Probe:** `tools/jg2_probe.py`. It prints a HELD, REFUTED or NOT RUN line for each prediction, a
VERDICT line and a DIGEST, and has a `--sabotage` switch that skips the byte change in P6. Under
sabotage, P6 must be REFUTED and the probe must exit 1.

## Next unrun test

Run P5–P7 on the S25 under Termux (`pkg install openssh`). That is the Android part of S1 and S3.
