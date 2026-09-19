# C1 lead-8 direction recovery from T0 side — preregistration

Issue #511. Parent #507 / #493 / #483 / #450.

## Objective

Conditional on a retrospective C1 turn occurring within the next 8 native bars, test whether the current causal T0 signal side anticipates the direction of that turn.

## Frozen inputs

- T0 signal bars from the period-21 own-lifecycle breakout engine;
- compression_score and B1..B5 walk-forward bands exactly as frozen in #507;
- retrospective dense C1=S0-S1 turn oracle for evaluation only.

## Turn event

For a T0 signal bar k, find the first C1 turn in (k,k+8].

If none exists, the row is not part of the direction-recovery denominator.

Future turn direction:
- TO_UP
- TO_DOWN.

## Prediction

T0 side is the only directional predictor:

- LONG predicts TO_UP
- SHORT predicts TO_DOWN.

No fitted model, no threshold and no future label enters the prediction.

## Primary zone

High-compression zone = B4 or B5.

This is frozen from the prior accepted risk-ranking study; B5 alone is reported as a stricter low-support diagnostic.

Low-compression comparator = B1 or B2.

## Primary outputs

For high-compression turn events:

- N
- T0-side directional accuracy
- LONG->TO_UP accuracy
- SHORT->TO_DOWN accuracy
- year-by-year accuracy.

Also report the same for B5 alone, B1+B2, and all bands.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 resamples, seed 20260919.

Report 95% CI for:
- high-compression directional accuracy minus 0.50;
- high-compression accuracy minus low-compression accuracy.

## Gate

C1_LEAD8_T0_DIRECTION_RECOVERY_SUPPORTED iff:

1. high-compression accuracy >0.50;
2. bootstrap 95% lower bound for high-compression accuracy >0.50;
3. high-compression accuracy >0.50 in at least 2 of 3 test years;
4. both LONG and SHORT point accuracies >0.50;
5. high-compression accuracy is not lower than low-compression accuracy.

Otherwise:

C1_LEAD8_T0_DIRECTION_RECOVERY_NOT_SUPPORTED.

## Boundary

No T0 PnL, C1 PnL or routing outcome.

A positive result would identify a causal direction precursor only; it would not yet authorize trading.