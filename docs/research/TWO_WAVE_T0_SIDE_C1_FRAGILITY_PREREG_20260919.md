# T0-side C1 proxy fragility by compression — preregistration

Issue #561. Parent #558 / #507 / #493 / #450.

## Universe

Use authoritative #507 strict-boundary v2 walk-forward scored T0 signal bars for 2018-2020 only.

Compression bands B1..B5 and compression_score are frozen exactly from #507; no recomputation or retuning.

## Proxy

Proxy direction = actual T0 trade side at signal bar k.

## Targets

- current target: retrospective dense C1=S0-S1 native slope sign at k;
- future8 target: retrospective dense C1 slope sign at k+8.

Targets are evaluation-only.

## Metrics

For current and future8 separately report by B1..B5:
- N
- accuracy
- balanced accuracy
- UP recall
- DOWN recall.

Also report pooled baseline fidelity across all bands.

## Primary fragility estimand

For future8 balanced accuracy:

Delta_future8 = BA(B5) - BA(B1).

Negative means high compression makes T0 side less reliable as a C1 direction proxy.

Secondary current estimand:

Delta_current = BA_current(B5) - BA_current(B1).

## Bootstrap

20-trading-day calendar blocks, 5,000 resamples, seed 20260919.

Report 95% CI for Delta_future8 and Delta_current.

## Gate

`T0_SIDE_C1_PROXY_FRAGILITY_SUPPORTED` iff:

1. pooled current balanced accuracy >=0.60;
2. pooled future8 balanced accuracy >=0.55;
3. future8 B5 < B1;
4. bootstrap 95% upper bound for Delta_future8 <0;
5. future8 band-rate Spearman rho <= -0.70;
6. B5 future8 BA < B1 in at least 2 of 3 years;
7. current B5 <= current B1 as a supporting consistency check.

Otherwise:

`T0_SIDE_C1_PROXY_FRAGILITY_NOT_SUPPORTED`.

## Boundary

No PnL, no route outcome, no proxy search, no band/threshold retuning.