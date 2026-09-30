# Operational Telemetry (Baseline Sensor)

**Status:** Operational only — **not** an epistemic component of Sovereign Veritas.

## Public label

`sv_automated_traffic_baseline`

## Purpose

Establish a measurable baseline of automated repository scraping (bots, mirrors, CI scanners) as background ecosystem noise.

## What is not published here

The live sensor endpoint / token URL is **not** published in this repository, in commits, issues, or screenshots.

Store the actual endpoint privately (operator-side only).

## How to interpret a trigger

Record as **token retrieval observed**, not **attack detected**.

Preserve alert details privately as operational evidence when useful:

- timestamp
- source IP
- user-agent
- token ID (private)

Do not rotate merely because the token fired; first preserve the alert details. If the live URL was previously exposed in a public commit, treat that endpoint as compromised for secrecy purposes and rotate privately; the public tree should continue to show only the neutral label.

## Human auditors

No action required. This section documents that a sensor exists; it is not part of Gate, package verification, or scientific claims.
