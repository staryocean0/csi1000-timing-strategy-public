# Inverse-OLS32 causal C1 direction carrier — independent-period preregistration

Issue #547. Parent #535 / #533 / #507 / #450.

## Hypothesis

Discovery atlas #535 found raw-price OLS direction systematically anti-aligned with retrospective C1=S0-S1 direction.

Freeze the primary causal carrier:

INV_OLS32(k) = -sign(OLS slope of log-close over bars k-31..k).

No future bars are used.

## Validation universe

Use period-21 T0 signal bars from 2015–2017 only.

This period was not used in the #535 directional-carrier atlas universe.

Require k+8 to lie inside the frozen retrospective dense C1 oracle support.

## Targets

Primary:
- retrospective dense C1 slope sign at k+8.

Secondary:
- retrospective dense C1 slope sign at k.

Targets are evaluation-only.

## T0 relation / independence

At each signal bar, recover the frozen T0 side from the period-21 trade ledger.

Report:
- carrier aligned fraction with T0
- carrier opposed fraction with T0
- future+8 balanced accuracy separately on aligned and opposed subsets.

The opposed subset is the critical incremental-information check.

## Primary gate

INV_OLS32_VALIDATED_AS_CAUSAL_C1_CARRIER iff all are true:

1. pooled future+8 balanced accuracy >=0.55;
2. 20-trading-day block bootstrap 95% lower bound for pooled future+8 balanced accuracy >0.50;
3. at least 2 of 3 years have future+8 balanced accuracy >=0.52;
4. no validation year has future+8 balanced accuracy <0.50;
5. T0-opposed subset support >=15% of scored signals;
6. T0-opposed subset future+8 balanced accuracy >0.52;
7. 20-trading-day block bootstrap 95% lower bound for T0-opposed subset future+8 balanced accuracy >0.50.

Otherwise:

INV_OLS32_NOT_VALIDATED_AS_CAUSAL_C1_CARRIER.

## Secondary controls

Also report INV_OLS42 / INV_OLS64 / INV_OLS86 on the same universe.

They are descriptive controls only and cannot replace INV_OLS32 in this study regardless of performance.

## Bootstrap

Calendar 20-trading-day blocks, 5,000 repetitions, seed 20260919.

## Boundary

No T0 PnL, no routing outcome, no threshold search, no model fitting.

Validation is independent-period development evidence, not fresh production OOS.