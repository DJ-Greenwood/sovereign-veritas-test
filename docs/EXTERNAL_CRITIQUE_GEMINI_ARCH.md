# External analysis — Gemini, architecture extrapolation (2026-10-03)

## Provenance

**Author: Gemini**, an external AI system. Its reply names the model as "Gemini 1.5 Pro/Flash"; that is the
model's own statement and is not verified here. Chad Holland asked it to extrapolate the low-level SV
prototype into a versatile, high-level architecture, and brought the answers into this repository. A note
from **ChatGPT** on how to read them came with them. All are stored verbatim and unedited in `docs/external/`:

| File | Author | sha256 |
|---|---|---|
| `gemini_2026-10-03_structural_analysis.md` | Gemini | `bff504ce16b41d8cd06b3e04e4aa07481afe826782d1a51df031310b11a275bf` |
| `gemini_2026-10-03_enterprise_architecture.md` | Gemini | `2944817a78e2f830494ffc4472b494743dacce34b1f4b9eb208c7dd48fc47063` |
| `gemini_2026-10-03_versatile_middleware.md` | Gemini | `9ec475da4fe375e762efeba53e4d3ea47c5d26bb06d562883a1d083edaa46393` |
| `gemini_2026-10-03_reply_to_review.md` | Gemini (reply to the review below) | `6679d93fd975944d4ba10bc0469590db5685b15741f33726bc4df18921e92a54` |
| `chatgpt_2026-10-03_extrapolation_note.md` | ChatGPT | `8d52b8aae50d41655e4dbecb317ce34cbba22c72be561c9c898216be0acdc4d9` |

The review below was written with Claude (Claude Opus 5.5); Chad read the summary, not each line.
The analyses are **external material, not this project's position** (C-EXT). The enterprise and
middleware files answer a design question; they describe nothing that exists in this repository.

## Checked against the repository (commands run 2026-10-03, origin/main 4eda7d4)

| claim in the Gemini analysis | check | result |
|---|---|---|
| `verify_package.py` imports no kernel code | `grep -nE "^\s*(from\|import) .*sovereign_veritas" tools/verify_package.py` | no lines: **holds** |
| 4,690 conformance vectors | `wc -l contract/gate_vectors.jsonl` | `4690`: **holds** |
| standard library only | `pyproject.toml` | `dependencies = []`: **holds** (tests need pytest) |
| GPS spoof 61 m outside the fence | README line 39, docs/VEHICLE_ACTION.md | **holds** (SITL, not hardware) |
| a DEFAULTED value can never pass as an explicit input | `tools/g1_recount.py` R6a (PR #26): a DEFAULTED runtime with an authorized request | **ALLOW: does not hold.** The value is labelled DEFAULTED in the package, but the Gate counts it healthy (README line 170 says so, citing docs/INTEGRATION.md finding F1). Refusing it is G1-6, not built |
| 103.8 °C is a threshold at which the gate shifts | docs/EVIDENCE_PACKAGE.md T6 | **does not hold.** One measured reading from one run; limits are uncalibrated (`s25-uncalibrated-v0`) |
| the gate shifts to "unconditional DEFER or REFUSE" | `sovereign_veritas/thermal_policy.py` docstring | **imprecise.** hot gives DEFER; unknown gives REFUSE |
| the system is "air-gapped" | `tools/witness.py`, signing | **does not hold.** The freshness witness is pushed to GitHub; signatures use the external `ssh-keygen` |

## Corrections to Gemini's reply (`gemini_2026-10-03_reply_to_review.md`)

The reply accepts the corrections above and drafts a version of this file. Its draft is **not** used,
because it adds claims of its own:

- It gives a reason for the DEFAULTED behaviour ("to prevent breaking backward-compatibility interfaces").
  No such reason is recorded in the repository.
- It says the lease-token idea violates "the invariant verified by the `gate_replay` check". `gate_replay`
  recomputes a recorded decision; it does not stop a package being used twice. Replay of a package is
  attack A7, closed by the consumed-token check (G1-3, `tools/consumer.py`).
- It calls G1-2 "the sequential command latch". G1-2 is the V13 **disagreement** latch (3 readings over the
  limit to latch; docs/VEHICLE_ACTION.md).
- It states that G1-1 and G1-2 "must be registered within the domain policy module". No such module exists,
  and that split is a proposal (below), not a decision.
- It describes its own first answer as hallucination. The architecture files were answers to a design
  question Chad asked; their errors are the four failed checks above, not the act of extrapolating.
- Its status line ("RECORDED | REFUTED | ARCHITECTURAL ALIGNMENT REGISTERED") is not this project's vocabulary.

## What is useful

1. **Already done, not new.** The proposed research question (a second implementation reproducing the
   same decisions on the same vectors; ChatGPT phrased it most precisely) is C6 in
   `docs/GATE_CONTRACT.md`: a Go port written from `CONTRACT.md` alone, 0 mismatches on its first run,
   checked by the `port-go` CI job. That holds for **sv.gate/0** only.
2. **Proposal: three layers.** Core invariants (evidence, provenance, replay, admissibility, freshness),
   domain policy (geofence, navigation, transaction limits), and the adapter that performs the effect.
   Under that split G1-1 (`nav_status`) and G1-2 (the latch) are drone policy. Not adopted; it would change
   the sv.gate/1 scope, so it needs Chad's decision.
3. **Proposal: contract first for every sv.gate/1 rule.** Rule text in `CONTRACT.md`, new vectors, Python,
   then the Go port, so C6 stays true for gate/1 instead of being a one-time result for gate/0.
4. **Door (unregistered).** A second, non-drone domain on the same core would test whether the three-layer
   split holds. Not registered; nothing built.

## Rejected for now

- The enterprise stack (Kafka, WASM sidecars, Envoy, QLDB). Nothing here is established at the scale it
  assumes; no claim requires it.
- The "lease token" cache: skipping re-evaluation for a matching fingerprint is the replay path G1-3 was
  built to close. If it is ever wanted, it should first be registered as an attack target.
