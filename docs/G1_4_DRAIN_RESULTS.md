# G1-4 drain results: a budget needs both a per-session and a shared per-target count

Registration: docs/G1_4_DRAIN_PREREG.md (804d5dc), committed before the probe existed.
Probe: `tools/g1_4_drain_probe.py`, x86-64 container, Python 3.13.15. **NOT VALIDATED on the S25.**
Claude-assisted (Claude Opus 5.5); Chad has not reviewed the code or this text. Not independent review.

## Failures and limits first
- **No prediction failed, and that is weak evidence.** The arms are my own prototypes, written to the designs I
  registered; the probe mostly confirms they do what I meant (M10). The only part from the real code is that
  every request is individually ALLOWed by `Gate.evaluate`, and that sv.gate/0 has no budget (G0 column).
- **Sabotage only partly discriminates.** With budgets disabled, D5 fails and the digest changes (exit 1), but
  D3 and D4 still hold, because they predict a budget *failing*, and a disabled budget also fails.
- **AB's shared counter is assumed.** This repo has no state shared between consumers. AB holding K3 shows
  what a shared counter would buy, not that one exists.

## Result
```
cell   G0    A    B   AB   registered
K0      4    4    4    4   (4, 4, 4, 4)  AS REGISTERED
K1     10    5    5    5   (10, 5, 5, 5)  AS REGISTERED
K2     10    5   10    5   (10, 5, 10, 5)  AS REGISTERED
K3     10   10    5    5   (10, 10, 5, 5)  AS REGISTERED
HELD    D1
HELD    D2
HELD    D3
HELD    D4
HELD    D5
HELD    D6
VERDICT 6 of 6 as registered
DIGEST 77c3c2c273ed30739f29cd44ccc60c064a47a3d69ac1b7e705404b9f1ef7fc53
```

## What it means
- sv.gate/0 has no defence against drain: 10 of 10 in every attack cell.
- **A consumer-side budget (like G1-3) is split by using two consumers.** **A gate-side budget read from the
  session chain is split by opening sessions.** Each closes one route and leaves the other.
- So "checked at the gate" in docs/SV_GATE_1_SCOPE.md is not enough on its own if a requester can open
  sessions, and a consumer-only check is not enough if there is more than one consumer.
- The real decision for G1-4 is therefore **where shared state lives** (and how the verifier sees it), not the
  budget rule itself. That is a design decision for Chad, and it changes the scope doc's wording.

## Door (M15)
The real G1-4 registration (state store, verifier view, contract-first through CONTRACT.md, vectors, Python,
Go port). Unregistered.
