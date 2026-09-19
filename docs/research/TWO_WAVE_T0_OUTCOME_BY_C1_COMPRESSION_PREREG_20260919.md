# T0 outcome stratification by causal C1 compression-risk bands — preregistration

Issue #537. Parent #507 / #493 / #450.

## Frozen input

Use the strict-boundary #507 walk-forward scored T0 signal ledger.

The compression score, feature ECDFs and B1..B5 cutpoints are immutable.

No score retraining, threshold movement, relabeling, or outcome-based band merging.

## T0 outcome

Join each scored signal bar to the frozen period-21 T0 own-lifecycle closed trade.

Outcome = `net_log_return_proxy`, reported in bp.

Also report win rate, fast-loss rate and duration.

## Per-band outputs

For B1..B5 pooled and each test year 2018/2019/2020:

- N
- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration
- q10/q25/q75/q90 net bp.

## Primary economic contrasts

1. `D51 = mean_net(B5) - mean_net(B1)`
2. `DHL = mean_net(B4+B5) - mean_net(B1+B2)`
3. fast-loss difference `FL_HL = fast_loss(B4+B5) - fast_loss(B1+B2)`

Positive compression risk is economically adverse when D51 and DHL are negative and FL_HL is positive.

## Inference

Use 20-trading-day calendar blocks of scored T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CIs for D51, DHL and FL_HL.

## Economic-degradation gate

`C1_COMPRESSION_T0_ECONOMIC_DEGRADATION_SUPPORTED` iff:

1. pooled D51 <0 and bootstrap 95% upper bound <0;
2. pooled DHL <0 and bootstrap 95% upper bound <0;
3. pooled FL_HL >0 and bootstrap 95% lower bound >0;
4. B5 mean net < B1 mean net in at least 2 of 3 test years.

Otherwise:

`C1_COMPRESSION_T0_ECONOMIC_DEGRADATION_NOT_SUPPORTED`.

## Boundary

This study may establish that high C1-turn risk is economically harmful to T0.

It may NOT select a veto band or production rule.

Any veto threshold requires a separate preregistered study.