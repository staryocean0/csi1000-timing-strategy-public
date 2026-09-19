# C1 causal-state fragility across compression-risk bands — preregistration

Issue #549. Parent #507 / #493 / #483 / #450.

## Objective

Determine whether the fully causal compression score from #507 is best interpreted as a confidence/fragility variable for the currently visible causal C1 leg.

## Frozen scored input

Use the authoritative #507 v2 walk-forward scored T0-signal ledger:

- SHA256: `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- test years: 2018 / 2019 / 2020
- risk_band B1..B5 and compression_score are frozen; do not recompute or retune.

## Causal C1 state

At each signal bar k:

- build scale-specific continuity hierarchy depth 3;
- use `_prepare_asof(stage1)` + `causal_state(..., k)`;
- if RESOLVED, causal leg sign is +1 for UP, -1 for DOWN.

Coverage is reported. No retrospective information enters this state.

## Retrospective evaluation oracle

Use the same dense C1=S0-S1 retrospective slope-sign oracle as #483/#507.

For each scored signal k record:

- oracle_sign_now = sign(dC1(k))
- oracle_sign_8 = sign(dC1(k+8))
- turn_next8 = whether an oracle C1 turn occurs in (k,k+8].

The oracle is evaluation-only.

## Primary fragility population

Primary analysis is restricted to signals where:

1. causal C1 state is RESOLVED;
2. causal leg sign equals oracle_sign_now.

This means the causal state is retrospectively correct at the decision clock.

Define endpoint invalidation:

`invalidated_8 = 1[oracle_sign_8 != causal_C1_sign]`.

With the frozen turn process, also report `turn_next8` as a companion event.

## Outputs

For B1..B5 and pooled:

- resolved N
- current fidelity = P(causal sign == oracle_sign_now)
- primary-population N
- invalidation_8 rate
- turn_next8 rate
- future fidelity = 1 - invalidation_8.

Also report each year separately.

## C1 relation to T0

Map causal C1 leg relative to T0 side:

- ALIGNED
- OPPOSED.

Within each relation, report B1/B5 invalidation_8 and turn_next8 point rates.

These are robustness diagnostics, not independent hard gates.

## Bootstrap

Use 20-trading-day calendar blocks of scored T0 signal bars.

Bootstrap 5,000 resamples, seed 20260919.

Primary bootstrap estimands on the current-correct population:

- B5 minus B1 invalidation-rate difference
- B5/B1 invalidation risk ratio.

## Fragility gate

`C1_COMPRESSION_STATE_FRAGILITY_SUPPORTED` iff all are true:

1. causal C1 resolved coverage >=95%;
2. current-correct primary population >=70% of resolved signals;
3. pooled B5 invalidation rate > pooled B1;
4. bootstrap 95% lower bound for B5-B1 invalidation difference >0;
5. bootstrap 95% lower bound for B5/B1 invalidation risk ratio >1;
6. invalidation rates across B1..B5 have Spearman rho >=0.70;
7. B5 invalidation > B1 in at least 2 of 3 years.

Otherwise:

`C1_COMPRESSION_STATE_FRAGILITY_NOT_SUPPORTED`.

## Boundary

No T0 PnL or routing outcome is used.

A positive result would justify using compression as a confidence modifier on causal C1 state, but not yet as a trading veto.