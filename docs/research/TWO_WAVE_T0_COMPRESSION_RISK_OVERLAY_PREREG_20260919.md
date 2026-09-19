# T0 causal compression-risk overlay — preregistration

Issue #523. Parent #507 / #493 / #450.

## Objective

Test whether the fully causal compression score from #507 directly ranks T0 own-lifecycle trade quality, without using any current C1 direction estimate.

## Universe

Use the exact 2018-2020 T0 signal bars and frozen walk-forward compression_score / risk_band B1..B5 from #507.

Score construction and band cutpoints are not recomputed or retuned.

## T0 outcome

Join each scored signal bar to the frozen period-21 own-lifecycle T0 trade:

- net_log_return_proxy
- net_bp
- win
- fast_loss
- duration.

## Per-band outputs

For B1..B5 pooled and by year:

- N
- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration.

Also report LONG/SHORT separately.

## Primary risk-overlay inference

Use 20-trading-day calendar-block bootstrap, 5,000 resamples, seed 20260919.

Primary paired contrasts:

- mean_net_bp(B5)-mean_net_bp(B1)
- fast_loss_rate(B5)-fast_loss_rate(B1).

## Risk-overlay gate

T0_COMPRESSION_RISK_OVERLAY_SUPPORTED iff all are true:

1. pooled B5 mean net < pooled B1 mean net;
2. bootstrap 95% upper bound for B5-B1 mean-net difference <0;
3. pooled band mean-net Spearman rho <= -0.70;
4. pooled B5 fast-loss rate > B1 fast-loss rate;
5. bootstrap 95% lower bound for B5-B1 fast-loss difference >0;
6. B5 mean net < B1 mean net in at least 2 of 3 test years.

Otherwise:

T0_COMPRESSION_RISK_OVERLAY_NOT_SUPPORTED.

## Hard-veto gate

T0_COMPRESSION_HARD_VETO_SUPPORTED only if risk-overlay gate passes AND:

1. B5 pooled mean net bp <0;
2. 20-day block-bootstrap 95% upper bound for B5 mean net bp <0;
3. B5 mean net bp <0 in at least 2 of 3 test years.

If risk-overlay passes but hard-veto does not:

T0_COMPRESSION_RISK_OVERLAY_SUPPORTED_BUT_NOT_HARD_VETO.

## Boundary

This is consumed development evidence only.

No score tuning, feature search or threshold search is allowed in this study.