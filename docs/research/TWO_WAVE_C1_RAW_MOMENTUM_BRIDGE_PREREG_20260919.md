# C1 lead-8 raw-momentum bridge — preregistration

Issue #531. Parent #529 / #507 / #485 / #450.

## Objective

Test a fully causal raw-price bridge for forecasting retrospective dense C1 slope sign 8 bars later.

## Frozen universe

Use exact #507 strict-v2 T0 signal bars for 2018–2020.

## Causal inputs at signal bar k

- ret_8 = log(close[k]/close[k-8]);
- sign(ret_8);
- frozen #507 strict-v2 risk_band.

Rows with ret_8=0 or zero future oracle C1 slope sign are excluded from directional scoring and coverage is reported.

## Targets

- current oracle sign = final retrospective dense C1=S0-S1 native slope sign at k;
- future oracle sign = same at k+8.

Targets are for evaluation only.

## Forecasts

Baseline RAW_PERSIST:
- predict future C1 sign = sign(ret_8).

Candidate RAW_COMPRESSION_FLIP:
- if risk_band in HIGH = B4+B5, predict -sign(ret_8);
- otherwise predict sign(ret_8).

HIGH is inherited from #515 and not retuned.

## Outputs

- scoring coverage;
- sign(ret_8) vs current oracle accuracy/balanced accuracy;
- baseline future accuracy/balanced accuracy;
- candidate future accuracy/balanced accuracy;
- paired candidate-minus-baseline correctness difference;
- by-year and by-band results.

## Bootstrap

20-trading-day calendar blocks, 5,000 resamples, seed 20260919.

Report 95% CI for candidate-minus-baseline accuracy difference.

## Gate

C1_RAW_MOMENTUM_LEAD8_FORECAST_SUPPORTED iff all are true:

1. scoring coverage >=0.95;
2. raw-momentum vs current-oracle balanced accuracy >=0.55;
3. candidate future balanced accuracy >=0.55;
4. candidate future balanced accuracy exceeds baseline by at least 0.02;
5. bootstrap 95% lower bound for paired candidate-minus-baseline accuracy difference >0;
6. candidate future accuracy exceeds baseline in at least 2 of 3 years.

Otherwise:

C1_RAW_MOMENTUM_LEAD8_FORECAST_NOT_SUPPORTED.

## Boundary

No T0 PnL or route outcome is used.