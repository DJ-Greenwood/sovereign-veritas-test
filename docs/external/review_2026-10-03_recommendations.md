The highest-value recommendation is to narrow the project’s claim and harden the boundary between **declared evidence, authorization, and real-world execution**.

## Priority 1: Fix execution semantics

This is the most urgent engineering problem. The system should never rely on “execute, then write the ledger” for actions that must not be duplicated or lost.

Implement a durable action state machine:

```text
PROPOSED
  → CLAIMED
  → EXECUTING
  → SUCCEEDED
  → FAILED
  → UNKNOWN
```

Use a unique idempotency key for every action. Before execution:

1. Persist the intent durably.
2. Atomically claim the idempotency key.
3. Refuse duplicate claims.
4. Execute through an idempotent executor.
5. Persist the result.
6. Reconcile `UNKNOWN` outcomes instead of blindly retrying.

A useful record might contain:

```json
{
  "action_id": "unique-action-id",
  "request_digest": "...",
  "policy_digest": "...",
  "principal": "...",
  "resource": "...",
  "state": "EXECUTING",
  "attempt": 1,
  "created_at": "...",
  "claimed_at": "...",
  "completed_at": null,
  "external_operation_id": "..."
}
```

Do not call an action “authorized” merely because its package verifies. Use separate states such as:

- `VERIFIED`
- `AUTHORIZED`
- `CLAIMED`
- `EXECUTED`
- `OUTCOME_CONFIRMED`

## Priority 2: Make evidence provenance explicit

Every input should carry provenance rather than just a value:

```json
{
  "value": 72,
  "source": "thermal_sensor_4",
  "kind": "measured",
  "observed_at": "...",
  "expires_at": "...",
  "measurement_id": "...",
  "attestation": "..."
}
```

At minimum, distinguish:

- measured;
- cryptographically attested;
- derived;
- operator-supplied;
- model-generated;
- defaulted;
- unknown.

A default value must never satisfy a high-risk authorization rule unless the policy explicitly says so. For high-consequence actions, missing, stale, defaulted, or unauthenticated evidence should produce `DEFER` or `REFUSE`.

## Priority 3: Separate authorization from truth

The project should state its guarantee in a more precise way:

> The system verifies that a package is well-formed, signed when applicable, and consistent with a declared policy and declared inputs.

It should not imply that the package proves the inputs were truthful.

Then add a formal **input trust policy**:

```text
sensor reading:
  authenticated: yes
  maximum age: 2 seconds
  replay protection: required
  trusted source: device attestation

GPS:
  authenticated: no
  cross-check: inertial + radio + map constraints
  high-risk use: prohibited without corroboration
```

This would turn “we verify evidence” into a concrete statement about which evidence is trusted and why.

## Priority 4: Build a genuinely independent verifier

The current separate verifier is a good start, but an independent implementation would provide much stronger evidence.

Recommended approach:

- Keep the Python implementation as the reference.
- Write a second verifier in Rust or Go.
- Give the second implementer only `CONTRACT.md` and the test vectors.
- Do not share internal helper code.
- Run differential tests across both implementations.
- Require byte-for-byte agreement on:
  - decision;
  - reason code;
  - normalized input;
  - package digest;
  - signature payload;
  - failure classification.

The contract should define every edge case, especially serialization and failure ordering.

## Priority 5: Formalize canonical serialization

Cryptographic digests are only useful if every implementation hashes exactly the same bytes.

Document and test:

- UTF-8 encoding;
- Unicode normalization;
- key ordering;
- number representation;
- treatment of negative zero;
- rejection of `NaN` and infinity;
- duplicate JSON keys;
- line endings;
- trailing whitespace;
- absent versus `null`;
- timestamps;
- binary data;
- maximum field sizes.

Reject ambiguous input instead of silently normalizing it. A malicious package should not be able to produce different interpretations in different languages.

## Priority 6: Improve key management

Add a formal key lifecycle:

- key identity and owner;
- permitted actions;
- permitted resources;
- validity interval;
- key version;
- revocation status;
- rotation procedure;
- compromise recovery;
- signature algorithm and parameters;
- trusted root or delegation chain.

A signature should answer more than “which key signed this?” It should also answer “was this key authorized to approve this exact kind of action at that time?”

For high-risk actions, consider threshold approval:

```text
operator approval + device approval
```

rather than relying on one signing key.

## Priority 7: Add replay and freshness protections

The witness log is useful, but it should be supplemented with:

- explicit expiration times;
- monotonic sequence numbers;
- nonce or challenge binding;
- policy-version binding;
- runtime-state version binding;
- key-revocation checks;
- external or multi-party timestamps;
- log inclusion and consistency proofs.

A package should fail if it is valid but too old for the action being authorized.

## Priority 8: Define a threat model and trust boundary

Add a concise threat model to the repository. For each component, state whether it is:

- trusted;
- authenticated but not trusted for truth;
- untrusted;
- physically controlled;
- remotely compromiseable;
- able to modify evidence;
- able to replay evidence;
- able to suppress evidence.

The most important question is: **what happens if the caller, sensor adapter, filesystem, signing key, or executor is compromised?**

The answer should be expressed as explicit security properties, not general language such as “sovereign” or “veritas.”

## Priority 9: Strengthen testing

Add these test categories:

- property-based tests for the Gate;
- fuzzing for package parsing;
- differential tests against the independent verifier;
- concurrency tests;
- crash-injection tests;
- filesystem corruption tests;
- replay and stale-package tests;
- revoked-key tests;
- policy-version mismatch tests;
- resource-exhaustion tests;
- malformed Unicode and numeric tests.

The existing mutation testing is a strong foundation. Extend it to the execution coordinator, package parser, signature handling, and witness log.

## Priority 10: Simplify the public API

Expose a small, difficult-to-misuse API. For example:

```python
decision = verifier.evaluate(request)
authorization = executor.authorize(decision, evidence)
result = executor.execute(authorization)
```

Avoid APIs where callers can directly construct fields such as:

```python
authorized=True
status="PASS"
```

If labels are needed for display, derive them inside the trusted code. Caller-controlled labels should be renamed to something unmistakable, such as `caller_label` or `untrusted_annotation`.

## Suggested roadmap

### Phase 1: Security correctness

- Fix duplicate-action handling.
- Add durable intent records.
- Represent unknown execution outcomes.
- Remove authorization power from defaults.
- Add explicit evidence provenance.
- Document the threat model.

### Phase 2: Verifier confidence

- Specify canonical serialization.
- Build a second-language verifier.
- Add differential and fuzz testing.
- Add package-size and resource limits.
- Add key rotation and revocation.

### Phase 3: Operational readiness

- Add persistent storage abstraction.
- Add crash recovery.
- Add observability without leaking sensitive evidence.
- Add policy versioning and migration.
- Add compatibility guarantees for package formats.
- Conduct an external security review.

### Phase 4: High-consequence use

Only after the earlier phases should the system be considered for physical or financial actions. Even then, use it as one layer in a defense-in-depth architecture—not as the sole safety mechanism.

The best near-term product would be a **verifiable policy-decision and execution-intent system for reversible actions**, such as sandboxed tool calls, staged deployments, or bounded API operations. That scope would demonstrate the architecture’s value without making claims it cannot yet support.