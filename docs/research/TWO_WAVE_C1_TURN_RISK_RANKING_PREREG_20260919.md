# Causal C1 turn-risk ranking at T0 signal bars — preregistration

Issue #498. Parent #493 / #485 / #483 / #450.

## Objective

Test whether the lead-8 compression precursor can causally rank the risk that C1 will turn within the next 8 native 5m bars at actual T0 signal decision bars.

## Decision universe

Use closed T0 period-21 breakout trades only for their signal bars.

The ranking study does not use the T0 trade outcome.

## Target

Retrospective dense C1=S0-S1 native-slope oracle.

For a T0 signal bar k:

turn_next8 = 1 iff at least one retrospective C1 slope-sign turn occurs in bars (k,k+8].

Otherwise turn_next8 = 0.

## Causal features at k

- abs_ret_8
- range_8
- rv_8
- efficiency_8

No future bars are used in these features.

## Walk-forward score construction

Test years: 2018, 2019, 2020.

For test year Y:

1. training reference bars are T0 signal bars from years strictly before Y;
2. for each feature, compute the empirical percentile of the test value in the prior-year reference distribution;
3. lower feature percentile means stronger compression;
4. feature compression score = 1 - percentile;
5. total compression_score = equal-weight mean of the four feature compression scores.

No target label, PnL, fitted coefficient or hyperparameter is used to build the score.

## Metrics

Per year and pooled:

- AUROC
- average precision
- baseline turn_next8 rate
- score quintile turn rates
- top 10% turn rate and lift vs baseline
- top 20% turn rate and lift vs baseline

Direction diagnostic among true turns:

- accuracy of predicting future turn direction as opposite sign(ret_8).

## Block bootstrap

For pooled top-10% lift:

- cluster by 20-trading-day blocks of T0 signal dates
- 5,000 bootstrap resamples
- seed 20260919
- report 95% CI for top10 turn-rate / baseline turn-rate.

## Acceptance

`C1_CAUSAL_TURN_RISK_RANKING_SUPPORTED` iff all hold:

1. pooled AUROC > 0.55;
2. at least 2 of 3 test years have AUROC > 0.52;
3. pooled top-10% lift >=1.50;
4. bootstrap 95% lower bound for top-10% lift >1.0;
5. pooled Spearman correlation between score quintile index and quintile turn rate >0.

Otherwise:

`C1_CAUSAL_TURN_RISK_RANKING_NOT_SUPPORTED`.

## Boundary

No PnL or routing outcome.

A positive ranking result only authorizes later threshold selection and integration studies.