# C1 causal state persistence vs compression risk — preregistration

Issue #521. Parent #507 / #493 / #450.

## Objective

Test whether the fully causal compression risk score from #507 predicts the stability of the currently observable C1 relation to T0 over the next 8 native bars.

## Universe

Use the exact 2018-2020 T0 signal bars and walk-forward compression score/bands B1..B5 from #507.

No rescoring, rebucketing or retuning.

## Current causal C1 relation

At T0 signal bar k:

- obtain the then-known stage1 causal state via the accepted causal_state resolver;
- use its current leg UP/DOWN;
- map relative to T0 side:
  - ALIGNED if causal C1 leg matches T0 side;
  - OPPOSED if causal C1 leg opposes T0 side;
  - UNRESOLVED if causal C1 state is unavailable.

UNRESOLVED rows are reported for coverage but excluded from binary persistence scoring.

## Future oracle C1 relation

At k+8, use the frozen retrospective dense C1=S0-S1 native slope sign oracle from #483.

Map future oracle sign relative to T0 side as:

- FUTURE_ALIGNED
- FUTURE_OPPOSED.

Exact-zero oracle slope at k+8 is excluded and reported.

## Primary outcomes

1. transition_8 = 1 if future oracle relation differs from current causal relation;
2. persistence_8 = 1-transition_8.

Report by compression band B1..B5:

- N
- transition rate
- persistence rate.

Also report separately for current causal C1 ALIGNED and OPPOSED.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

5,000 resamples, seed 20260919.

Primary intervals:

- pooled transition-rate difference B5-B1;
- ALIGNED persistence difference B5-B1;
- OPPOSED persistence difference B5-B1.

## Support gates

C1_COMPRESSION_STATE_TRANSITION_SUPPORTED iff all are true:

1. pooled transition rate B5 > B1;
2. bootstrap 95% lower bound for pooled transition B5-B1 >0;
3. pooled transition-rate Spearman across B1..B5 >=0.70;
4. current-ALIGNED persistence B5 < B1;
5. bootstrap 95% upper bound for ALIGNED persistence B5-B1 <0;
6. current-OPPOSED persistence B5 < B1;
7. bootstrap 95% upper bound for OPPOSED persistence B5-B1 <0;
8. pooled B5 transition > B1 in at least 2 of 3 test years.

If overall transition ranking passes but one current-relation branch fails, verdict is:

C1_COMPRESSION_TRANSITION_PARTIAL_BRANCH_SUPPORT.

Otherwise:

C1_COMPRESSION_STATE_TRANSITION_NOT_SUPPORTED.

## Boundary

No T0 PnL, trade-return or route outcome is used.

A positive result establishes only a causal C1 state-transition prior.