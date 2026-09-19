# Causal C1 turn-risk ranking using local-background compression — preregistration

Issue #505. Parent #503 / #498 / #493 / #450.

## Objective

Test whether the accepted local-background compression variables can causally rank imminent C1-turn risk at actual T0 signal bars.

## Universe

T0 period-21 signal bars.

## Target

turn_next8 = 1 iff the retrospective dense C1=S0-S1 slope oracle turns within (k,k+8].

## Accepted causal features

Use only the three #503-supported variables:

1. abs_ret8_over_range32
2. range8_over_range32
3. efficiency8_minus_efficiency32

rv8_over_rv32 is excluded because it failed direction robustness in #503.

## Walk-forward score

Test years: 2018, 2019, 2020.

For each test year:

- prior-year T0 signal bars only form the reference distribution;
- compute each test feature's empirical percentile in that prior-year distribution;
- lower percentile = stronger local compression;
- component score = 1 - percentile;
- total risk score = equal-weight mean of the three component scores.

No fitted coefficients and no target labels enter score construction.

## Metrics

Per year and pooled:

- AUROC
- average precision
- baseline turn rate
- score-quintile turn rates
- top10 turn rate / lift
- top20 turn rate / lift

Direction diagnostic among true turns:

- future turn direction predicted as opposite sign(ret_8).

## Bootstrap

Top10 lift pooled:

- 20-trading-day T0-signal blocks
- 5,000 resamples
- seed 20260919
- 95% interval.

## Acceptance

`C1_LOCAL_BACKGROUND_TURN_RISK_RANKING_SUPPORTED` iff:

1. pooled AUROC >0.55;
2. at least 2/3 test years AUROC >0.52;
3. pooled top10 lift >=1.50;
4. top10 lift bootstrap 95% lower bound >1.0;
5. pooled quintile turn-rate Spearman >0.

Otherwise:

`C1_LOCAL_BACKGROUND_TURN_RISK_RANKING_NOT_SUPPORTED`.

## Boundary

No PnL or route outcome.

A positive result only authorizes later threshold/state integration work.