# Causal C1 directional carrier atlas beyond T0 horizon — preregistration

Issue #535. Parent #533 / #531 / #507 / #450.

## Objective

Find causal direction carriers that are not mechanically identical to the period-21 T0 breakout direction.

## Frozen universe

Use exact #507 strict-v2 T0 signal bars for 2018–2020.

## Frozen horizons

- 32 bars
- 42 bars
- 64 bars
- 86 bars

These correspond to >T0, 2×T0, about 3×T0, and the median C1/T1 period.

## Carrier families

For each horizon H:

1. RETURN_H = sign(log(close[k]/close[k-H]))
2. OLS_H = sign(OLS slope of log-close over bars k-H+1..k)

Only bars <=k are used.

## Evaluation targets

Retrospective dense C1=S0-S1 native slope sign:

- current oracle sign at k
- future oracle sign at k+8

Targets are evaluation-only.

## Outputs

For each carrier:

- coverage
- current-oracle accuracy / balanced accuracy
- future+8 accuracy / balanced accuracy
- fraction aligned to T0 side
- fraction opposed to T0 side
- year-by-year future+8 balanced accuracy
- year-by-year opposed fraction.

## Boundary

This is an atlas only.

No carrier is selected, ranked, or promoted from this study.

No PnL or routing outcome is used.