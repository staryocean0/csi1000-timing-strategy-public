# C1 lead-8 turn-direction recovery from recent 8-bar return — preregistration

Issue #574. Parent #507 / #493 / #483 / #450.

## Objective

Conditional on a retrospective C1 turn occurring within the next 8 native bars, test whether the turn direction can be recovered causally from the current 8-bar return.

## Universe

Authoritative #507 v2 scored T0 signal bars, years 2018–2020, with turn_next8=1.

Target window must remain inside the frozen C1 oracle support exactly as in #507 v2.

## Target

Use the same dense retrospective C1=S0-S1 native-slope oracle.

For a signal bar k with turn_next8=1, identify the unique C1 slope-sign turn in (k,k+8].

Target classes:
- TO_UP
- TO_DOWN.

## Predictor

At signal bar k:

`predicted_turn_direction = -sign(ret_8)`

where `ret_8 = log(close[k]/close[k-8])`.

Rows with exact ret_8=0 are excluded and reported.

No fitted parameter, model, weight or threshold.

## Metrics

Pooled and by year:
- N
- ordinary accuracy
- balanced accuracy
- recall TO_UP
- recall TO_DOWN.

Also report accuracy by frozen #507 risk band B1..B5 and pooled B4+B5 as diagnostics only.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for pooled accuracy and balanced accuracy.

## Gate

`C1_LEAD8_DIRECTION_RECOVERY_SUPPORTED` iff all are true:

1. pooled balanced accuracy >=0.60;
2. bootstrap 95% lower bound for balanced accuracy >0.55;
3. recall TO_UP >0.55;
4. recall TO_DOWN >0.55;
5. ordinary accuracy >0.55 in at least 2 of 3 test years.

Otherwise:
`C1_LEAD8_DIRECTION_RECOVERY_NOT_SUPPORTED`.

## Boundary

No T0 PnL or routing outcome.

A positive result supplies only the direction component of a later causal C1 state forecast.