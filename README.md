# Sovereign Veritas

<!-- 30s-demo -->
> **Status labels used below.** **PROTOTYPE:** runs, is tested, and is not hardened for production.
> **RESEARCH HYPOTHESIS:** stated, not yet shown. **NOT PRODUCTION-READY:** nothing in this repository is.

**Headline (measured):** a package whose authorization was revoked *and whose digests were all
resealed* still fails verification, because the verifier recomputes the Gate's decision from the
recorded inputs (`gate_replay`). A full verify takes about 125–143 ms on a container, Python
start-up included.

### 30-second demo — PROTOTYPE

```bash
git clone https://github.com/holland202/sovereign-veritas && cd sovereign-veritas
python tools/demo_30s.py          # standard library only; exit 0 only if every line is as expected
```

See the repository for measured demo output and negative results (fully consistent rewrite still verifies; CONSISTENT is not world-truth).

<!-- /30s-demo -->

A fail-closed permission gate for AI actions. Before an action runs, the Gate decides
ALLOW, DEFER or REFUSE, and the decision can be written into an evidence package that a
separate verifier, sharing no code with this package, rebuilds and checks from the file alone.

Developed and run on a Galaxy S25 in Termux. Standard library only. The kernel makes no network
calls and has no telemetry; one optional red-team tool calls NVIDIA's API when you run it.

## Try it — about 5 minutes, Python 3.10+

```bash
git clone https://github.com/holland202/sovereign-veritas
cd sovereign-veritas
python -m pip install -e ".[test]"
python -m pytest -q
python tools/make_package.py --thermal-status normal
python tools/verify_package.py /path/to/the/package.json
```

Full measurement tables, signing, witness log, vehicle/model tools, and contract vectors: see the remainder of this repository and `docs/`.

## Authority boundary

```text
Adversary ----X----> Veritas Gate
```

If custody fails, the registry does not change.

## Operational Telemetry (Baseline Sensor)

This repository maintains a neutral operational traffic sensor under the label `sv_automated_traffic_baseline`.

Purpose: establish a measurable baseline of automated repository scraping (bots, mirrors, CI scanners) as background ecosystem noise.

This is **not** an epistemic component of the Sovereign Veritas architecture. The live sensor endpoint is **not** published in this repository. Human auditors need not act on this section.

A trigger is recorded as **token retrieval observed**, not as an attack detection. Alert details (timestamp, source, user-agent) are retained privately for operational baseline measurement.

See [docs/OPERATIONAL_TELEMETRY.md](docs/OPERATIONAL_TELEMETRY.md).

## License and credit

MIT. You may use, change, share and sell this, including commercially, on one condition: keep the
copyright notice (`Copyright (c) 2026 Chad Holland`) and the license text with every copy or
substantial portion. That is the credit the license requires.

If you use Sovereign Veritas in work you publish — a paper, a product, a post — please also cite
it. GitHub's **Cite this repository** button gives the format (from `CITATION.cff`).
