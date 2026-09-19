# C1 causal-state fragility across compression-risk bands — result

Issue #549. Parent #507 / #493 / #483 / #450.

## Verdict

`C1_COMPRESSION_STATE_FRAGILITY_NOT_SUPPORTED`

The authoritative #507 compression score does rank the probability of a retrospective C1 turn within the next 8 bars, but it does **not** behave as a confidence/fragility modifier for the currently visible causal C1 leg.

## Input

Frozen authoritative #507 v2 scored ledger:

`6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`

Scored 2018–2020 T0 signals: 945.

## Current causal-C1 fidelity

Causal C1 state is resolved on:

- 945 / 945 = **100%**

But among resolved signals, the causal leg sign matches the final retrospective C1 slope sign at the same bar only:

- **351 / 945 = 37.14%**

Band-specific current fidelity:

- B1: 32.39%
- B2: 35.32%
- B3: 41.48%
- B4: 36.87%
- B5: 37.85%

Therefore the main limitation is not missing coverage. The currently visible causal C1 leg is often not the same object as the final retrospective C1 current slope sign.

## Primary current-correct population

Primary population requires causal C1 to be resolved and correct at k.

N = 351.

Endpoint invalidation within 8 bars:

- B1: **23.91%**
- B2: 18.18%
- B3: 23.16%
- B4: 25.76%
- B5: **14.93%**

Thus B5 is not more fragile than B1.

Pooled:

- B5 − B1 invalidation difference: **−8.99pp**
- B5 / B1 risk ratio: **0.624**
- band-rate Spearman: **−0.30**

20-trading-day block bootstrap:

- B5−B1 95% CI: **[−24.09pp, +5.93pp]**
- B5/B1 95% CI: **[0.258, 1.426]**

No fragility gate passes.

## Year stability

B5 invalidation exceeds B1 in only 1 of 3 test years.

2018:
- B1 36.36%
- B5 16.67%

2019:
- B1 9.09%
- B5 12.50%

2020:
- B1 25.00%
- B5 15.79%

## Relation-to-T0 diagnostics

Among current-correct causal C1 states:

Causal C1 ALIGNED to T0:
- B1 invalidation 35.48%
- B5 invalidation 6.06%

Causal C1 OPPOSED to T0:
- B1 invalidation 0%
- B5 invalidation 23.53%

These are descriptive only and were not preregistered as independent gates.

## Interpretation

The compression score remains useful as a **global C1 turn-risk ranking** from #507.

But it should not be interpreted as:

> “high compression means the currently visible causal C1 leg is less trustworthy.”

The deeper problem is that the current causal C1 leg itself has only ~37% contemporaneous fidelity to the final retrospective C1 slope sign.

Therefore the next research problem is:

> **find a better causal proxy for the current C1 direction before using compression as a timing/turn-risk dimension.**

## Evidence

Implementation SHA256:

`928a483946ef0b781383430abf2cb5572f01808f2a52be7d93fe5f722ae88260`

Fragility ledger SHA256:

`3c9d3e90246d6e2fbb0297475bdba2d7040f03e6f2d9d6c9bedb54f073024b83`

Exact result SHA256:

`cd0a9aa5d59e4b17f270fd2ae5e868c3598fb3a8e12412d5512db0ed1a3430ab`

## Authority

No T0 PnL or route outcome was used.

No signal/router/trade/paper/live/production authority.
