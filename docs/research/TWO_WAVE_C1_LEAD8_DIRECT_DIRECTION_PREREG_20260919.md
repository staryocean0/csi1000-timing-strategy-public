# C1 lead-8 causal direction predictor from raw/T0 structure — preregistration

Issue #604. Parent #601 / #507 / #483 / #450.

## Objective

Predict the final retrospective dense C1=S0-S1 native-slope direction at k+8 from information available at a T0 signal bar k.

This is a direct causal direction-recognition study. It deliberately excludes the high-level C1 anchors rejected by #601.

## Decision universe

Use closed period-21 T0 breakout trades from the frozen research engine.

Decision clock = trade signal bar k.

Only signal bars with k+8 inside the frozen dense-C1 oracle support are eligible.

## Target

Retrospective label:

- UP if dC1(k+8)>0
- DOWN if dC1(k+8)<0
- zero sign -> excluded.

The target is research-only and is never used as an input.

## Allowed causal features at k

### Raw path

- ret_4
- ret_8
- ret_16
- ret_32
- range_8 / range_16 / range_32
- rv_8 / rv_16 / rv_32
- efficiency_8 / efficiency_16 / efficiency_32

### Latest completed base/T0-wave structure known by k

- last_base_g
- last_base_slope_per_bar
- last_base_height
- last_base_duration
- age_since_last_base_confirmation
- previous_base_g
- base_same_sign_run
- last_base_direction (categorical)
- last_two_base_same_sign (categorical)

### Current T0 opportunity

- T0 trade side LONG/SHORT (categorical).

## Explicitly forbidden inputs

- causal C1 leg
- causal C1 descriptor
- causal C1 phase
- causal C1 age/amplitude
- confirmed S0/S1 segment slopes
- compression target/turn label
- T0 PnL or future return.

## Model

One fixed sklearn pipeline:

- numeric: median imputation fit on training only + StandardScaler;
- categorical: most-frequent imputation fit on training only + OneHotEncoder(handle_unknown='ignore');
- LogisticRegression:
  - C=1.0
  - class_weight='balanced'
  - solver='lbfgs'
  - max_iter=2000
  - random_state=20260919.

No hyperparameter search or feature selection.

## Walk-forward

Test years: 2018 / 2019 / 2020.

For test year Y:

- train only on T0 signal rows with year <Y;
- require target bar k+8 to be strictly before the first bar of Y;
- all imputers/scalers/encoders/model fitting use training rows only;
- score the test year once.

## Metrics

Pooled and by year:

- N
- class counts
- balanced accuracy
- accuracy
- recall UP
- recall DOWN
- ROC AUC using predicted UP probability.

Also report the same metrics by frozen #507 compression band when the signal bar exists in the authoritative v2 score ledger, as diagnostics only.

## Bootstrap

20-trading-day calendar blocks of test T0 signals.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for pooled balanced accuracy.

## Acceptance gate

`C1_LEAD8_DIRECT_DIRECTION_SUPPORTED` iff all are true:

1. pooled balanced accuracy >=0.55;
2. pooled ROC AUC >0.55;
3. pooled recall UP >=0.52;
4. pooled recall DOWN >=0.52;
5. at least 2 of 3 test years have balanced accuracy >=0.52;
6. block-bootstrap 95% lower bound for pooled balanced accuracy >0.50.

Otherwise:

`C1_LEAD8_DIRECT_DIRECTION_NOT_SUPPORTED`.

## Stop rule

If rejected, do not tune the same logistic model or add post-hoc selected features against the exposed 2018–2020 results.

## Authority

No T0 PnL, routing, paper/live, trade or production authority.