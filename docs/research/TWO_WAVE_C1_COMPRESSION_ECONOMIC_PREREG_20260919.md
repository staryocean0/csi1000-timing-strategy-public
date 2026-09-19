# Economic relevance of causal C1 compression risk on T0 trades — preregistration

Issue #519. Parent #507 / #493 / #450.

## Objective

Test whether the accepted no-lookahead C1 compression ranking has economic relevance for actual T0 own-lifecycle trades.

## Frozen input

Use the strict-boundary #507 scored T0 signal ledger only.

- test years: 2018–2020
- scored signals: 945
- compression_score construction: unchanged
- risk bands B1..B5: unchanged, prior-year calibrated

No score refit, feature change, threshold search or band regrouping.

## Causal C1 context

At each T0 signal bar k, use the existing then-known causal C1 state:

`causal_state(_prepare_asof(stage1), k)`

Map causal C1 leg relative to the T0 side:

- ALIGNED
- OPPOSED

Unresolved rows are excluded and reported.

## T0 outcome

Use the frozen period-21 T0 own-lifecycle trade corresponding to the signal bar.

Primary outcome:

`net_log_return_proxy` in bp.

Also report:

- win rate
- fast-loss rate
- duration

## Primary branch

Causal C1 = ALIGNED.

Primary comparison:

- B1 = least compressed / lowest C1-turn risk
- B5 = most compressed / highest C1-turn risk

Pre-audit support before outcome inspection:

- ALIGNED B1: 42 trades
- ALIGNED B5: 70 trades

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

5,000 resamples, seed 20260919.

Report 95% CI for:

- mean net bp in B1
- mean net bp in B5
- difference `mean(B5)-mean(B1)`
- win-rate difference
- fast-loss-rate difference

## Gate Q — economic quality gradient

`C1_COMPRESSION_T0_QUALITY_GRADIENT_SUPPORTED` iff:

1. B1 and B5 each have >=30 trades;
2. B1 mean net bp >0;
3. mean(B5)-mean(B1) <0;
4. bootstrap 95% upper bound for mean(B5)-mean(B1) <0;
5. B5 win rate < B1 win rate;
6. year-specific point difference mean(B5)-mean(B1) is negative in at least 2 of 3 years.

## Gate V — veto candidate

`C1_COMPRESSION_T0_VETO_CANDIDATE_SUPPORTED` iff Gate Q passes and:

1. B5 mean net bp <0;
2. bootstrap 95% upper bound for B5 mean net bp <0.

If Gate Q passes but Gate V fails, interpretation is:

`QUALITY_GRADIENT_ONLY__NOT_A_VETO`.

## Secondary OPPOSED diagnostic

For causal C1 = OPPOSED, report the same B1/B5 metrics.

This branch is descriptive only. A positive B5-minus-B1 effect would be consistent with high turn risk helping an opposed C1 state flip toward T0, but no rule is accepted from it.

## Boundary

Development evidence only.

No live/paper/production authority.