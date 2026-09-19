# T0-conditioned C1 state: inverted direction proxy × compression fragility — preregistration

Issue #557. Parent #554 / #552 / #549 / #507 / #493 / #483 / #450.

## Objective

Test whether a T0-conditioned causal C1 representation can be decomposed into:

- current direction proxy = negative causal first-stage skeleton leg;
- fragility = frozen #507 compression risk band.

## Frozen universe

Use authoritative #507 v2 walk-forward scored T0-signal ledger:

- SHA256 `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- 2018–2020
- N=945.

## Direction proxy

At signal bar k:

- causal first-stage leg sign = +1 UP / -1 DOWN;
- C1 direction proxy = negative of that sign.

No fitting or threshold.

## Evaluation oracle

Retrospective dense C1=S0-S1 slope sign is used only for evaluation.

Record:

- oracle_sign_now at k;
- oracle_sign_8 at k+8;
- frozen #507 turn_next8.

## Primary population

Primary analysis requires:

1. causal skeleton state resolved;
2. inverted direction proxy equals oracle_sign_now.

Define:

`invalidated_8 = 1[oracle_sign_8 != direction_proxy]`.

## Outputs

Overall:

- proxy coverage;
- current direction fidelity;
- UP/DOWN recall.

On the current-correct primary population, B1..B5:

- N;
- invalidation_8 rate;
- turn_next8 rate;
- future direction fidelity.

Also report by year.

## Bootstrap

Use 20-trading-day calendar blocks.

5,000 resamples, seed 20260919.

Primary estimands:

- B5 minus B1 invalidation-rate difference;
- B5/B1 invalidation risk ratio.

## Gate

`T0_C1_DIRECTION_FRAGILITY_STATE_SUPPORTED` iff all are true:

1. proxy coverage >=95%;
2. current direction fidelity >=60%;
3. pooled B5 invalidation rate > pooled B1;
4. bootstrap 95% lower bound for B5-B1 invalidation difference >0;
5. bootstrap 95% lower bound for B5/B1 invalidation ratio >1;
6. invalidation-rate Spearman across B1..B5 >=0.70;
7. B5 invalidation > B1 in at least 2 of 3 years.

Otherwise:

`T0_C1_DIRECTION_FRAGILITY_STATE_NOT_SUPPORTED`.

## Boundary

No T0 PnL or routing outcome.

A positive result would qualify a causal C1 direction+fragility representation for a later T0 outcome study.