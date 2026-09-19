# Two-Wave C2/C3 bandpass routing roadmap amendment — insert R2b

Date: 2026-09-19.

Parent thread: #450. Trigger: R2 #458.

## Why the roadmap changes

R2 proved that the final exact retrospective C2/C3 bandpass morphology is structurally too delayed for direct live routing.

Key evidence:

- C2 exact slope median delay: 369 native 5m bars
- C3 / joint exact state median delay: 1561 bars
- joint exact availability:
  - +8: 0%
  - +16: 0%
  - +32: 0%
  - +64: 0%
  - +128: 0%
  - +256: 0.3846%
  - +512: 3.6642%
- prefix replay passed at 10k / 30k / 50k

Therefore the problem is not look-ahead leakage. The problem is structural confirmation latency.

## Authority consequence

The thread does **not** abandon the C2/C3 bandpass state concept.

Instead it inserts a new observation layer:

`R2b_CAUSAL_BANDPASS_STATE_RECOGNIZER_OR_CARRIER`

The execution-routing stages are paused until R2b produces an accepted causal observation state.

## Revised execution order

1. R0 — explicit C2/C3 bandpass representation freeze — **DONE**
2. R1 — intrinsic retrospective morphology atlas — **DONE**
3. R2 — exact causal observability audit — **DONE / direct exact state rejected for live routing**
4. R2b — causal bandpass recognizer/carrier — **ACTIVE NEXT**
5. R3 — fair E0=T0 / E1=T1-C1 execution contract
6. R4 — bandpass-to-execution discovery atlas
7. R5 — candidate state-machine preregistration
8. R6 — independent validation

## R2b role

R2b is an observation problem, not a routing problem.

It may use only information available at knowledge time k.

Its target is the frozen retrospective C2/C3 bandpass morphology from R0/R1.

Primary fidelity dimensions must include:

- C2 and C3 residual level fidelity
- C2 and C3 slope fidelity
- slope-sign fidelity
- joint relation identity
- turn timing
- excess-turn / oversegmentation
- causal delay
- temporal stability
- prefix replay

No T0/C1 execution outcome may be visible during carrier/recognizer selection.

## What remains forbidden

Until R2b passes:

- no C2/C3-based T0/C1 router training
- no route PnL optimization
- no post-hoc state cell selection
- no backfilling final retrospective C2/C3 states into live decision times
- no production/paper/live authority

## Next action

Create a separate R2b preregistration that compares causal observation families against the frozen bandpass oracle without execution outcomes.

The family design must not be selected using T0/C1 route performance.
