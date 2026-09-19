# T0 economic interaction with causal C1 compression risk bands — preregistration

Issue #612. Parent #507 / #493 / #450.

## Frozen risk input

Use authoritative #507 v2 walk-forward scored T0-signal ledger unchanged.

Scored ledger SHA256:
`6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`

Risk bands B1..B5 were built using prior-year-only feature ECDFs and cutpoints.

## T0 economic outcome

Join by signal_bar to frozen period-21 own-lifecycle T0 trades:

- close breakout
- next-open fill
- own exit/reversal lifecycle
- 2bp per side proxy cost.

Primary outcomes:

- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration.

## Primary contrast

B5 most-compressed versus B1 least-compressed.

Report:

- mean-net difference B5-B1
- fast-loss-rate difference B5-B1
- year-by-year B5/B1 means
- pooled band table B1..B5.

## Bootstrap

20-trading-day calendar blocks, 5,000 resamples, seed 20260919.

Report 95% CI for:

- B5-B1 mean-net difference
- B5-B1 fast-loss-rate difference
- B5 mean net itself.

## Verdict hierarchy

`C1_COMPRESSION_T0_VETO_SUPPORTED` iff:

1. B5 pooled mean net <0;
2. bootstrap 95% upper bound for B5 mean net <0;
3. B5 mean net <0 in at least 2 of 3 test years.

Otherwise `C1_COMPRESSION_T0_RISK_DOWNGRADE_SUPPORTED` iff:

1. pooled B5 mean net < pooled B1 mean net;
2. bootstrap 95% upper bound for B5-B1 mean-net difference <0;
3. pooled B5 fast-loss rate > pooled B1 fast-loss rate;
4. bootstrap 95% lower bound for B5-B1 fast-loss-rate difference >0;
5. B5 mean < B1 mean in at least 2 of 3 test years.

Otherwise:

`C1_COMPRESSION_T0_ECONOMIC_INTERACTION_NOT_SUPPORTED`.

## Boundary

No risk score or threshold is changed from #507.

Development evidence only; no live/production authority.