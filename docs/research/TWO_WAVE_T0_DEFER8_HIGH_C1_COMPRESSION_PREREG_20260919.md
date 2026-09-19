# High C1-compression T0 defer-8 confirmation audit — preregistration

Issue #540. Parent #537 / #507 / #493 / #450.

## Frozen input

Use the strict-boundary #507 walk-forward scored T0 signals.

High-risk group is fixed as `risk_band in {4,5}`.

No score threshold or risk band may be changed.

## Original T0

Period-21 own-lifecycle breakout trade:

- signal on close k;
- original entry open k+1;
- exit at original T0 reversal open;
- 4bp completed round-trip proxy cost.

## Defer-8 policy

For each high-risk signal at bar k:

1. observe bars through k+8;
2. delayed entry open = k+9;
3. if original T0 exit_bar <= k+9, do not trade and assign policy net return 0 for this signal;
4. otherwise enter at open k+9 in the original T0 side;
5. exit at the original T0 exit open;
6. executed deferred trade pays 4bp completed-trade proxy cost.

This preserves the original T0 direction and reversal lifecycle. Only entry timing changes.

## Primary estimand

For every high-risk signal, including skipped ones:

`delta_policy_bp = deferred_policy_net_bp - original_t0_net_bp`

Skipped signals have deferred policy return 0.

This per-signal estimand prevents survivor bias.

## Primary outputs

Pooled and by year:

- high-risk signal count
- deferred executed count
- deferred execution fraction
- original mean net bp
- deferred-policy mean net bp per signal
- mean delta_policy_bp
- median delta_policy_bp
- original win rate
- deferred policy positive-return fraction per signal
- original fast-loss rate
- fraction skipped by defer window.

## Mechanism diagnostics

Skipped signals:

- N
- original mean/median net bp
- original win rate
- original fast-loss rate
- original duration distribution.

Surviving signals:

- original mean net bp
- delayed executed mean net bp
- delayed-minus-original mean bp
- original vs delayed holding duration.

## Inference

Use 20-trading-day calendar blocks of high-risk signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for pooled mean `delta_policy_bp`.

## Defer-8 gate

`C1_COMPRESSION_DEFER8_SUPPORTED` iff all are true:

1. pooled mean delta_policy_bp >0;
2. block-bootstrap 95% lower bound for mean delta_policy_bp >0;
3. deferred-policy mean net bp per signal > original mean net bp;
4. at least 2 of 3 test years have positive mean delta_policy_bp;
5. skipped signals have negative point-estimate original mean net bp;
6. deferred execution fraction >=0.50.

Otherwise:

`C1_COMPRESSION_DEFER8_NOT_SUPPORTED`.

## Boundary

No alternative delays, score thresholds, or risk-band combinations are tested here.

A positive result would justify a later independent validation of defer-8; it would not authorize production.