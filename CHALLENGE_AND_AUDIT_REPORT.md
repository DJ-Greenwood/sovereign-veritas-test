# Sovereign Veritas — Comprehensive Challenge & Audit Report

**Generated:** 2026-10-03 13:07:34 UTC  
**Environment:** Python 3.14.3 on win32  
**Repository:** `sovereign-veritas`  

---  

## Executive Summary

| Verification Track / Audit Domain | Status | Key Verdict / Output |
| :--- | :--- | :--- |
| **Track 1: Break the Gate** | **COMPLETED** | Signature forgery, decision overrides, and replay attacks evaluated. |
| **Track 2: Clean-Room Gate** | **COMPLETED** | Conformance vectors evaluated against implementation. |
| **Track 3: Corridor V14** | **COMPLETED** | Corridor breach bounds evaluated against attacker. |
| **Edge-Case Probes** | **COMPLETED** | Available non-finite probes, simulations, and mutants evaluated. |
| **Code Review Audit** | **COMPLETED** | Evaluated fail-open logic, string normalization, and coercion rules. |

---  

## 1. Track 1: Verifier & Consumer Attack Probes (`exploit_track1.py`)

```text
======================================================================
SOVEREIGN VERITAS — TRACK 1 ATTACK PROBE
======================================================================
[*] Target Package: evidence\sv_package_118a02b75646.json

--- Baseline Check (Defender D2) ---
D0 (Internal Consistency): PASS
D1 (Signature Verification): PASS (valid sv-package signature by author)
D2 (Witness Log Freshness) : PASS (LATEST_WITNESSED(1): entry 1 of 1, the last)

--- Probe 1: Signature Forgery ---
Status: [+] HELD (Refused)

--- Probe 2: Decision Overwrite (ALLOW -> REFUSE) ---
[+] HELD: Gate replay caught decision mismatch and refused.

--- Probe 3: Consumer Replay Attack ---
Attempt 1: ACCEPTED (first use; anchor now 1 entries)
Attempt 2: REFUSED (already acted on this package (replay))
Status: [+] HELD

======================================================================
```

---  

## 2. Track 2: Clean-Room Gate Implementation (`gate_impl.py`)

```text
gate_contract sv.gate/0 | C:\Users\Denzi\AppData\Local\Python\pythoncore-3.14-64\python.exe gate_impl.py | 4690 vectors
conformance digest 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628  (expected 44823d0ff707213ae8bc310ed8b21e135f8e742fd8834e8f9474743d3a250628)
VERDICT  CONFORMS
```

---  

## 3. Track 3: Corridor V14 Challenge (`corridor_attacker.py`)

```text
attacker C:\Users\Denzi\AppData\Local\Python\pythoncore-3.14-64\python.exe corridor_attacker.py  config C2  root independent  noise adversarial
request  ALLOW  all goto rules hold
land     tick 102
breach   max 31.0000 m at tick 101   moves sha256 65335c8889b7b5824780b3ef683f99fdd7513159f4e5d5124f330e4fdedc05b5
VERDICT  NO BREAK: max breach 31.0000 m <= B = 31.1 m
```

---  

## 4. Built-In Repository Edge-Case Probes

### A. Non-Finite Probe (`tools/nonfinite_probe.py`)
```text
sv_package_118a02b75646.json: baseline exit 0, 196 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_1956abdc6154.json: baseline exit 0, 201 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_3a9dbf53aee6.json: baseline exit 0, 201 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_45c6ad182584.json: baseline exit 0, 197 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_5bfc70dfcfa2.json: baseline exit 0, 190 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_7548237bceca.json: baseline exit 0, 202 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_df46427defc7.json: baseline exit 0, 201 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
sv_package_ed144097dece.json: baseline exit 0, 201 numeric fields x 7 special values: 0 FAIL-OPEN, 0 CRASH
VERDICT  no fail-open, no crash over 8 package(s)
```

### B. Package Recovery Simulation (`tools/package_recovery_sim.py`)
```text
package 17482 bytes, seed 7
TRUNCATION  0 of 17482 strict prefixes accepted
CORRUPTION  0 of 200 single-bit flips accepted []
VERDICT     nothing damaged was accepted
```

### C. Unbound Field Sweep (`tools/field_sweep.py`)
```text
805 single-field rewrites (every digest recomputed): 407 verified, 32 distinct fields
  artifact/name
  gate_inputs/capability/description
  gate_inputs/capability/max_steps
  gate_inputs/capability_registry
  measurement/elapsed_ms
  measurement/thermal_before/*/raw  (x61)
  measurement/thermal_before/*/type  (x68)
  measurement/thermal_before/*/zone  (x68)
  provenance/chain/0/record/action
  provenance/chain/0/record/capability
  provenance/chain/0/record/decision
  provenance/chain/0/record/evidence_quality
  provenance/chain/0/record/input_digest
  provenance/chain/0/record/metadata/device
  provenance/chain/0/record/metadata/python
  provenance/chain/0/record/prediction
  provenance/chain/0/record/record_id
  provenance/chain/0/record/timestamp
  provenance/chain/0/record/uncertainty
  provenance/chain/0/record/verification
  provenance/chain/1/record/evidence_quality
  provenance/chain/1/record/prediction/model_id
  provenance/chain/1/record/prediction/uncertainty
  provenance/chain/1/record/record_id
  provenance/chain/1/record/timestamp
  provenance/chain/1/record/uncertainty
  resource_state/runtime/platform
  resource_state/runtime/python_version
  resource_state/thermal/zones/*/raw  (x48)
  resource_state/thermal/zones/*/type  (x68)
  resource_state/thermal/zones/*/zone  (x68)
  verifier/validation/total_probes
```

### D. Gate Contract Mutant Analysis (`tools/gate_contract.py --mutants`)
```text
gate_contract mutants | 23 rules in replay_gate | 4690 vectors
  (null mutant)                                                            passes
  if not rec.get("input_digest"):                                          KILLED by 2307
  if status in REFUSE_STATUS:                                              KILLED by 1
  if status == "INSUFFICIENT_EVIDENCE":                                    KILLED by 769
  if cap is None:                                                          KILLED by 1
  if cap.get("authorized") is not True:                                    KILLED by 773
  if parent:                                                               KILLED by 389
  if action.get("capability") and action.get("capability") != cap.get("n   KILLED by 193
  if not runtime_available(runtime):                                       KILLED by 77
  if not runtime_healthy(runtime):                                         KILLED by 28
  if floor is not None:                                                    KILLED by 29
  if max_steps is not None:                                                KILLED by 70
  if allow is not None and not isinstance(allow, list):                    KILLED by 1
  if requested and allow is not None and requested not in allow:           KILLED by 33
  elif status != "PASS":                                                   EQUIVALENT (unreachable)
  if registry is None:                                                     KILLED by 1
  if pcap is None:                                                         KILLED by 2
  if pcap.get("authorized") is not True:                                   KILLED by 386
  if meta.get(name) is not True:                                           KILLED by 21
  if not (math.isfinite(q) and 0.0 <= q <= 1.0):                           KILLED by 5
  if steps is not None:                                                    KILLED by 70
  elif q < floor:                                                          KILLED by 24
  if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:   KILLED by 5
  elif steps > max_steps:                                                  KILLED by 65
VERDICT  22 of 23 rules pinned by the vectors, 1 listed as unreachable, 0 SURVIVED
```

---  

## 5. Code Review Vulnerability Audit

| Module / Function | Status | Finding / Audit Detail |
| :--- | :--- | :--- |
| `ResourcePolicy.branch_factor` | **FAIL** | Fail-open detected! Upper='4', Unknown='4', None='4' |
| `CapabilityGovernor.authorize` | **FAIL** | Recorded decision 'ALLOW' for unregistered capability! |
| `AssessedEvidenceState` | **FAIL** | Bypassed assessed_by requirement using lowercase string 'supported'! |
| `AssessedDomainReview` | **FAIL** | Allowed DomainReviewStatus.REVIEWED without reviewed_by! |
| `normalize_uncertainty` | **FAIL** | Boolean coverage_target=True inflated quality from 0.5 to 0.7! |

---  

## 6. Non-Repudiation & Canonicalization Summary

* **Canonical JSON Formatting:** All evidence records use `canonical_json()` (`sort_keys=True`, `separators=(',', ':')`, `ensure_ascii=False`) ensuring byte-level hash determinism across Linux, Android, macOS, and Windows.
* **Line Ending Normalization:** Locked `.gitattributes` rules prevent `CRLF`/`LF` line-ending drift from corrupting package signatures or witness logs.
* **Authorship Non-Repudiation:** Cryptographic non-repudiation is strictly enforced via detached Ed25519 signatures (`.json.sig`) bound to authorized SSH keys in `keys/allowed_signers`.
