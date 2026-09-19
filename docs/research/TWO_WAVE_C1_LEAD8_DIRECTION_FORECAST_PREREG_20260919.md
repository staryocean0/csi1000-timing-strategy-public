# C1 causal lead-8 direction forecast — preregistration

Issue #529. Parent #507 / #493 / #483 / #450.

## Objective

Test whether current causal C1 leg direction plus the frozen causal compression risk state can forecast final retrospective C1 direction 8 native bars later.

## Frozen universe

Use exact #507 strict-v2 T0 signal bars for 2018–2020.

## Causal inputs at signal bar k

- then-known causal C1 current leg direction from accepted stage1 causal_state;
- frozen #507 strict-v2 risk_band B1..B5.

## Retrospective targets for evaluation only

- current oracle sign = final dense C1=S0-S1 native slope sign at k;
- future oracle sign = same at k+8.

Rows with unresolved causal C1 leg or zero oracle slope sign are excluded from directional scoring and their coverage is reported.

## Forecasts

Baseline PERSIST:
- predict k+8 direction = current causal C1 leg.

Candidate COMPRESSION_FLIP:
- if risk_band in HIGH = B4+B5, predict opposite current causal C1 leg;
- otherwise predict persistence.

HIGH threshold is inherited from #515 and is not retuned.

## Outputs

- causal C1 resolved coverage;
- current causal-leg vs current-oracle accuracy and balanced accuracy;
- future target UP/DOWN class balance;
- PERSIST accuracy/balanced accuracy;
- COMPRESSION_FLIP accuracy/balanced accuracy;
- paired candidate-minus-baseline correctness difference;
- results by year and by risk band.

## Bootstrap

Use 20-trading-day calendar blocks of scored T0 signals.

5,000 resamples, seed 20260919.

Report 95% CI for paired candidate-minus-baseline accuracy difference.

## Gate

C1_LEAD8_DIRECTION_FORECAST_SUPPORTED iff all are true:

1. causal C1 resolved coverage >=0.95;
2. current causal-leg vs current-oracle balanced accuracy >=0.55;
3. candidate future balanced accuracy >=0.55;
4. candidate future balanced accuracy exceeds baseline by at least 0.02;
5. bootstrap 95% lower bound for paired candidate-minus-baseline accuracy difference >0;
6. candidate future accuracy exceeds baseline in at least 2 of 3 test years.

Otherwise:

C1_LEAD8_DIRECTION_FORECAST_NOT_SUPPORTED.

## Boundary

No T0 PnL is used. A failed hard-flip forecast does not invalidate compression as a turn-risk/uncertainty state.