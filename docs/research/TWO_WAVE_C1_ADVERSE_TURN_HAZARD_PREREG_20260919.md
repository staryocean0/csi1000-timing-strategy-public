# C1 compression score as adverse-turn hazard for T0 — preregistration

Issue #579. Parent #507 / #577 / #493 / #450.

## Objective

Test whether the fully causal compression score ranks the probability that the first C1 turn within the next 8 native bars is adverse to the current T0 side.

## Universe

Use authoritative #507 v2 walk-forward T0 signal ledger for 2018-2020.

Reuse compression_score and prior-only risk_band B1..B5 exactly.

## T0 side

Recover the frozen period-21 T0 trade side from the same own-lifecycle breakout engine by exact signal_bar.

## Retrospective state target

For signal bar k:

- NO_TURN if no C1 slope-sign turn occurs in (k,k+8];
- otherwise take the first turn;
- ADVERSE_TURN if first turn direction != T0 side;
- FAVORABLE_TURN if first turn direction == T0 side.

The retrospective C1 oracle is evaluation-only.

## Outputs

For pooled and each test year:

- N
- any-turn rate
- adverse-turn rate
- favorable-turn rate
- adverse share among turns
- B1..B5 rates.

Continuous-score diagnostics:

- ROC AUC for ADVERSE_TURN vs all other signal bars
- ROC AUC for ANY_TURN, reported only as a consistency check against #507.

## Bootstrap

20-trading-day calendar blocks of T0 signal bars.

5,000 block resamples, seed 20260919.

Report pooled B5-B1 adverse-turn risk difference and B5/B1 adverse-turn risk ratio.

## Gate

C1_ADVERSE_TURN_HAZARD_SUPPORTED iff all are true:

1. pooled B5 adverse-turn rate > pooled B1;
2. bootstrap 95% lower bound for B5-B1 adverse risk difference >0;
3. bootstrap 95% lower bound for B5/B1 adverse risk ratio >1;
4. B5 adverse-turn rate > B1 in at least 2 of 3 years;
5. pooled adverse-turn ROC AUC >0.52;
6. among B5 signals with any C1 turn, adverse share >0.50.

Otherwise:

C1_ADVERSE_TURN_HAZARD_NOT_SUPPORTED.

## Boundary

No T0 PnL, route outcome, or trading threshold is used.

A positive result would justify testing compression as a causal T0 risk/veto input in a separate preregistered economic study.