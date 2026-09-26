# Across chip vendors — registration and results

Status: **Registered** (2026-09-26), before any run below. Results are appended under the
registration and never edited into it.

Why: the author asked for tests on Qualcomm, NVIDIA, AMD, Intel, Broadcom and Cerebras hardware.
docs/MODEL_ACTION.md already found that the same model file and prompt give different reply bytes
on the S25 (Qualcomm) and on this container's CPU (Intel), and that the version of llama.cpp was
not the cause. These tests ask which part of the platform is, and whether the Gate's guarantees
hold wherever the bytes differ.

## What hardware is actually available

| vendor | here | what can honestly be tested |
|---|---|---|
| Intel | this container: Xeon @ 2.10GHz with AVX2, AVX-512, AVX-VNNI, AMX | the same llama.cpp built for different instruction sets; thread count |
| Qualcomm | the S25 Ultra: Snapdragon 8 Elite (Oryon CPU, Adreno GPU, Hexagon NPU) | CPU (done in MODEL_ACTION); Adreno GPU through Vulkan if Termux's build has it; the NPU only if llama.cpp lists it |
| NVIDIA | no GPU; an NVIDIA API account (build.nvidia.com) | not the same model file on an NVIDIA GPU. What can run: `tools/nvidia_challenge.py`, an NVIDIA-hosted model trying to forge packages that the local verifier accepts |
| AMD | none | nothing. An AVX2-only build approximates an older x86 instruction set; it is not an AMD test and is not called one |
| Broadcom | none | nothing: no AI compute from Broadcom is reachable from here |
| Cerebras | none without an API key | a hosted model, as for NVIDIA, if a key is provided; not the same file |

## Registered predictions

All: Qwen2.5-1.5B-Instruct Q4_K_M (sha256 6a1a2eb6…), temperature 0, seed 1, `cache_prompt` off,
the three prompts of MODEL_ACTION (easy, hard, easy asking for delete_file), llama.cpp v0.4.1.

Intel (container):

- **X1** The native build (AVX-512 available) reproduces MODEL_ACTION's x86 bytes: easy
  `a97203ae`, hard `9d7f7234`.
- **X2** One thread and two threads give the same bytes (work is split across threads by rows;
  no sum crosses a thread).
- **X3** An AVX2-only build gives different bytes from the native build on at least one prompt.
- **X4** A build with no AVX at all (SSE4.2 only) differs from both on at least one prompt.
- **X5** In every build the check's verdicts are right by hand, and every refusal holds: whatever
  the bytes, a wrong answer is REFUSEd and delete_file is not allowed.

Qualcomm (S25, run in Termux):

- **Q1** The Adreno GPU through Vulkan (`-ngl 99`) runs, and its bytes differ from the phone CPU's
  `b3605c11` on at least one prompt.
- **Q2** On the GPU, the easy prompt sent three times gives the same bytes three times.
- **Q3** Every package made on the GPU verifies, and its `thermal_before` has readable `gpu`
  domain zones (the `gpu` limit of the thermal policy has never been exercised).
- **Q4 (may not be runnable)** `llama-server --list-devices` shows whether the NPU is usable. If it
  is not listed, Q4 is recorded as not runnable, not as a failure.

NVIDIA (hosted, run in Termux with the author's key):

- **N1** An NVIDIA-hosted model given one of the published S25 packages, the verifier's source and
  five rounds finds no forgery that the local verifier accepts outside the known limits K1-K3.

Stated limits: one run per case. Different bytes are not wrong answers; the claim under test for
the Gate is X5, not that bytes match.
