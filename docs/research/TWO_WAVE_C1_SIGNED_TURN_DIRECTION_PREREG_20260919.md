# C1 causal lead-8 signed turn-direction precursor — preregistration

Issue #609. Parent #507 / #493 / #483 / #450.

## Objective

Extend the accepted causal compression turn-risk ranking into a causal turn-direction precursor without fitting a classifier.

## Decision universe

Use exactly the authoritative #507 v2 scored T0 signal bars for 2018–2020.

Every row already has a prior-only compression_score.

## Causal direction input

At signal bar k, compute:

ret_8 = log(close[k]/close[k-8]).

Direction hypothesis:

- ret_8 < 0 -> if a turn occurs in next 8 bars, predict TURN_UP;
- ret_8 > 0 -> if a turn occurs in next 8 bars, predict TURN_DOWN;
- ret_8 == 0 -> no directional prediction.

## Directional hazard scores

- up_score = compression_score if ret_8 < 0 else 0
- down_score = compression_score if ret_8 > 0 else 0

No fitted weight, threshold, model or future label is used.

## Evaluation target

Using the frozen retrospective dense C1=S0-S1 oracle:

- find the first C1 native-slope sign turn in (k,k+8];
- if none -> NO_TURN;
- if first turn points positive -> TURN_UP;
- if first turn points negative -> TURN_DOWN.

The target is evaluation-only.

## Outputs

Overall and by year:

- class counts / rates: NO_TURN, TURN_UP, TURN_DOWN
- among actual turns with ret_8!=0: direction accuracy of -sign(ret_8)
- TURN_UP one-vs-rest ROC AUC using up_score
- TURN_DOWN one-vs-rest ROC AUC using down_score
- macro directional AUC = mean(AUC_UP,AUC_DOWN)
- mean compression_score by target class
- direction accuracy split by compression-score quintile from #507.

## Bootstrap

Use the same 20-trading-day calendar blocks as #507.

Bootstrap 5,000 block resamples, seed 20260919.

Report:

- 95% CI for turn-direction accuracy minus 0.50
- 95% CI for AUC_UP minus 0.50
- 95% CI for AUC_DOWN minus 0.50.

## Acceptance gate

C1_SIGNED_TURN_DIRECTION_PRECURSOR_SUPPORTED iff all are true:

1. pooled turn-direction accuracy >0.55;
2. bootstrap 95% lower bound for accuracy >0.50;
3. pooled AUC_UP >0.52;
4. pooled AUC_DOWN >0.52;
5. bootstrap 95% lower bound for both AUC_UP and AUC_DOWN >0.50;
6. turn-direction accuracy >0.50 in at least 2 of 3 test years;
7. macro directional AUC >0.54.

Otherwise:

C1_SIGNED_TURN_DIRECTION_PRECURSOR_NOT_SUPPORTED.

## Boundary

No T0 PnL or routing outcome.

A positive result establishes a causal C1 turn-risk-and-direction precursor only; it does not yet define a T0 veto.