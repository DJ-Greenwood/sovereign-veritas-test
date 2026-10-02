# Security Policy

Sovereign Veritas is a **research prototype**. It is **not production-ready**. Do not deploy it as a security boundary for real systems or people.

This repository intentionally documents known limitations and negative results. A `CONSISTENT` package means the package is internally consistent with the Gate’s rules and its recorded inputs. It does **not** establish that the recorded world state is true, that the Gate proves truth, or that the system is secure.

## Reporting findings

- **Public, reproducible findings** (bugs, contract mismatches, verification failures, attack results): open a GitHub Issue. Include:
  - commit or version
  - OS and Python version
  - exact steps to reproduce
  - expected result
  - actual result
  - raw output where useful

- **Sensitive information** that should not be disclosed publicly: still prefer a GitHub Issue with limited detail, or contact the repository owner via GitHub if disclosure would cause harm. There is no dedicated private security email.

Do not expect coordinated disclosure timelines or a vulnerability bounty. This is an open research project; careful, reproducible reports are the most useful contribution.

## Scope

- Key custody, production hardening, and operational security are out of scope of the current design.
- Published limits (e.g. fully consistent rewrites without signatures, freshness without a witness log) are documented in the README, CHALLENGE.md, and docs/; they are not “vulnerabilities” unless a claimed property is broken.

Thank you for testing carefully and reporting clearly.
