# C1 causal early-warning V1 — preregistration

Issue #492. Parents #485 / #483 / #450.

## Objective

Build the first genuine non-lookahead early-warning model for the retrospective C1=S0-S1 slope-turn oracle.

The model must use raw bars only.

No completed C1/C2 future descriptor, no retrospective hierarchy feature, no PnL.

## Decision schedule

Use the frozen C1 oracle support.

Decision bars are every 8 native 5m bars, anchored to the first support bar with enough 32-bar history.

Each decision interval is therefore non-overlapping:

`(k, k+8]`.

Target:

- `TURN_NEXT8=1` if at least one retrospective C1 slope turn occurs in (k,k+8];
- otherwise 0.

Because observed C1 turn spacing is >=8 bars, at most one target turn is expected in a decision interval.

For positive intervals, record the future turn direction TO_UP / TO_DOWN for direction diagnostics only.

## Raw causal features at k

All use bars <=k.

1. `log_abs_ret8 = log(abs(log(close[k]/close[k-8])) + 1e-8)`
2. `log_range8 = log(log(max(high[k-7:k]) / min(low[k-7:k])) + 1e-8)`
3. `log_rv8 = log(std(one-bar log returns over last 8 bars) + 1e-8)`
4. `efficiency8 = abs(net 8-bar log move) / total absolute one-bar log variation`
5. `log_range_ratio_8_32 = log((range8+1e-8)/(range32+1e-8))`
6. `log_rv_ratio_8_32 = log((rv8+1e-8)/(rv32+1e-8))`

No hierarchy state or future information is allowed.

## Model

Pipeline:

- StandardScaler
- LogisticRegression
  - C=1.0
  - class_weight='balanced'
  - max_iter=2000
  - random_state=20260919

No feature selection.
No hyperparameter search.

## Walk-forward

Test years:

- 2018
- 2019
- 2020

For each test year Y:

- train only on decision bars from years <Y;
- fit scaler and logistic model on training rows only;
- score test year once.

## Risk bucket

For each fold:

- compute training fitted probabilities;
- freeze the 80th percentile of training probability as the high-risk threshold;
- apply that threshold unchanged to the test year.

Report:

- test high-risk fraction
- event rate in high-risk bucket
- baseline event rate
- lift = high-risk event rate / baseline event rate
- recall of future turns captured by high-risk bucket

No test labels influence the threshold.

## Occurrence metrics

Per year and pooled:

- ROC-AUC
- average precision / PR-AUC
- baseline event rate
- Brier score

## Direction diagnostic

For positive target intervals:

- recent direction = sign(ret8)
- predicted new C1 direction = negative recent direction

If ret8=0, direction prediction abstains.

Report:

- direction coverage
- direction accuracy among all positive intervals
- direction accuracy among positive intervals that are also in the high-risk bucket

This is a diagnostic only.

## Acceptance

`C1_CAUSAL_WARNING_V1_ACCEPTED` iff all are true:

1. pooled ROC-AUC >=0.57;
2. at least 2 of 3 test years have ROC-AUC >=0.53;
3. each of at least 2 of 3 years has high-risk lift >=1.50;
4. pooled direction accuracy among high-risk captured turns >=0.60;
5. all features pass suffix-masking invariance checks.

Otherwise:

`C1_CAUSAL_WARNING_V1_NOT_READY`.

## Causality checks

For sampled decision bars in each test year:

- recompute all six features from a prefix ending at k;
- compare exactly to the full-data feature row;
- future suffix mutation must not change features at k.

Any failure blocks acceptance.

## Boundary

Development walk-forward only.
No fresh OOS.
No T0/C1 PnL.
No router/trade/production authority.
