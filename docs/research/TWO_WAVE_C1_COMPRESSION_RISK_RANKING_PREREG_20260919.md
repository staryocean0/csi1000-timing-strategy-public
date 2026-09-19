# C1 causal lead-8 compression risk ranking — preregistration

Issue #507. Parent #493 / #483 / #450.

## Objective

Build a fully causal, label-free compression risk score on actual T0 signal bars and test whether it ranks the probability of a retrospective C1 turn within the next 8 native bars.

## Decision universe

Use closed T0 period-21 breakout trades from the frozen own-lifecycle engine.

Decision clock = each trade signal bar k.

Only test years 2018, 2019, 2020 are scored.

## Causal features at k

- abs_ret_8
- range_8
- rv_8
- efficiency_8

All use bars <=k only.

## Walk-forward feature percentile calibration

For test year Y, training/calibration sample = T0 signal bars in all years <Y.

For each feature x, lower x means more compression.

Define reverse empirical percentile component:

r_x(k) = fraction of prior-year calibration observations with feature value >= x(k).

Thus larger r_x means stronger compression.

Score:

compression_score(k) = mean(r_abs_ret8, r_range8, r_rv8, r_efficiency8).

No labels, PnL, turn outcomes, fitted weights or hyperparameter search enter score construction.

## Walk-forward score bands

For each test year, compute the score distribution on the prior-year calibration sample using the same frozen feature ECDFs.

Freeze score cutpoints at calibration-score 20/40/60/80 percentiles.

Assign test-year signals into ordered bands B1..B5 using those prior-only cutpoints.

B1 = least compressed; B5 = most compressed.

## Research target

Using the frozen retrospective dense C1=S0-S1 oracle only for evaluation:

target=1 iff a C1 native-slope sign turn occurs in bars (k,k+8].

The target is never used to build the score or the band cutpoints.

## Outputs

For each year and pooled:

- scored N
- base turn-next8 rate
- N and turn rate in B1..B5
- B5/B1 risk ratio
- B5-B1 risk difference
- Spearman correlation between ordered band index and band turn rate
- ROC AUC of continuous compression_score as a descriptive ranking metric.

## Bootstrap

Primary uncertainty uses 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for pooled B5-B1 risk difference and pooled B5/B1 risk ratio.

## Ranking gate

C1_COMPRESSION_RISK_RANKING_SUPPORTED iff all are true:

1. pooled B5 turn rate > pooled B1 turn rate;
2. bootstrap 95% lower bound for B5-B1 risk difference >0;
3. bootstrap 95% lower bound for B5/B1 risk ratio >1;
4. pooled band-rate Spearman rho >=0.70;
5. B5 turn rate > B1 turn rate in at least 2 of 3 test years;
6. continuous pooled ROC AUC >0.52.

Otherwise:

C1_COMPRESSION_RISK_RANKING_NOT_SUPPORTED.

## Boundary

No T0 PnL is used.

A positive result establishes causal turn-risk ranking only, not a trading veto or threshold.