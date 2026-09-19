# C1 raw-return direction proxy family — independent validation preregistration

Issue #558. Parent #552 / #554 / #507 / #450.

## Purpose

Independently validate the fixed raw-return direction proxy family discovered on 2018-2020 T0 signal bars.

Validation period is 2015-2017 only and is not used to alter candidate windows or definitions.

## Frozen candidates

- RET8 = sign(log close[k]-log close[k-8])
- RET16 = sign(log close[k]-log close[k-16])
- RAW_MAJORITY = majority sign of RET8 / RET16 / RET32

No other window or combination is added after results.

## Universe

All frozen period-21 T0 signal bars in 2015, 2016, 2017 that lie inside retrospective dense C1=S0-S1 support and have nonzero target sign.

## Target

Retrospective dense C1=S0-S1 current native-slope sign at signal bar k.

Target is evaluation-only.

## T0-side baseline

Actual T0 trade side at the signal bar is recorded as a baseline direction proxy.

For each candidate report:

- fraction aligned with T0 side
- fraction opposed to T0 side
- pooled and yearly balanced accuracy versus C1 target
- UP/DOWN recall
- T0-side baseline balanced accuracy on the same rows
- candidate balanced-accuracy gain versus T0 side.

## Critical incremental-information subset

For each candidate, restrict to rows where candidate direction != T0 side.

Report:

- support fraction
- N
- balanced accuracy
- accuracy
- UP/DOWN recall
- 20-trading-day block-bootstrap 95% CI for balanced accuracy.

This subset is the critical test of whether the candidate contains C1 information not already encoded by T0 direction.

## Candidate validation gate

A candidate is independently validated iff all are true:

1. coverage >=95%;
2. pooled balanced accuracy >=0.60;
3. pooled UP recall >=0.55;
4. pooled DOWN recall >=0.55;
5. balanced accuracy >=0.55 in at least 2 of 3 years;
6. T0-opposed subset support >=15%;
7. T0-opposed subset balanced accuracy >0.52;
8. T0-opposed subset block-bootstrap 95% lower bound >0.50.

Otherwise that candidate is not validated as an incremental C1 direction proxy.

## Family verdict

`RAW_C1_PROXY_FAMILY_VALIDATED` iff at least 2 of the 3 frozen candidates pass the candidate gate.

Otherwise:

`RAW_C1_PROXY_FAMILY_NOT_VALIDATED`.

## Unique-primary rule

If at least two candidates validate, a unique primary may be named only if:

- top pooled BA exceeds runner-up by >=0.02; and
- 20-trading-day block-bootstrap 95% lower bound for top-minus-runner correctness >0.

Otherwise verdict includes:

`NO_UNIQUE_RAW_C1_PROXY`.

## Boundary

No PnL, compression score, future-turn target, route outcome or threshold optimization.