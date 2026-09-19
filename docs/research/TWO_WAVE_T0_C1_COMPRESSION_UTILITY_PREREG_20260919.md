# T0 utility audit of causal C1 compression risk bands — preregistration

Issue #582. Parent #507 / #493 / #450.

## Objective

Test whether the already-qualified, fully causal #507 C1 compression risk score has direction-agnostic risk-control value for actual T0 trades.

## Frozen universe

Use authoritative #507 v2 walk-forward scored T0 signal ledger:

- years: 2018–2020
- N = 945 scored T0 signal bars
- score/bands built with prior-year-only feature ECDFs and cutpoints
- no PnL entered #507 score construction.

Each signal bar is joined one-to-one to its frozen period-21 T0 own-lifecycle closed trade.

## Frozen risk states

Reuse #507 v2 exactly:

- B1 = least compressed / lowest C1-turn risk
- ...
- B5 = most compressed / highest C1-turn risk

No score, weight, cutpoint or band is retuned here.

## T0 outcome

Use the frozen T0 trade fields:

- net_log_return_proxy
- fast_loss
- duration

Report in basis points where applicable.

## Per-band outputs

For B1..B5 pooled and by year:

- N
- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration
- q10/q25/q75/q90 net bp.

Also report Spearman correlation of ordered band 1..5 with pooled:

- band mean net bp
- band fast-loss rate.

## Fixed primary contrast

Only B5 versus B1 is inferentially primary.

20-trading-day calendar-block bootstrap on T0 signal dates:

- 5,000 resamples
- seed 20260919.

Report 95% CI for:

1. Delta_net = mean_net_bp(B5) - mean_net_bp(B1)
2. Delta_fastloss = fast_loss_rate(B5) - fast_loss_rate(B1)
3. mean_net_bp(B5)

## CAUTION gate

`T0_C1_COMPRESSION_CAUTION_SUPPORTED` iff all are true:

1. point Delta_net < 0;
2. bootstrap 95% upper bound for Delta_net < 0;
3. point Delta_fastloss > 0;
4. bootstrap 95% lower bound for Delta_fastloss > 0;
5. B5 mean net < B1 mean net in at least 2 of 3 test years.

## HARD VETO gate

`T0_C1_COMPRESSION_HARD_VETO_CANDIDATE` iff CAUTION passes and:

1. pooled B5 mean net bp < 0;
2. bootstrap 95% upper bound for B5 mean net bp < 0.

If CAUTION passes but HARD VETO does not:

`T0_C1_COMPRESSION_CAUTION_ONLY`.

If CAUTION fails:

`T0_C1_COMPRESSION_UTILITY_NOT_SUPPORTED`.

## Interpretation boundary

This is consumed development evidence.

Even HARD VETO CANDIDATE would require a fresh holdout / paper-shadow confirmation before any live rule.
