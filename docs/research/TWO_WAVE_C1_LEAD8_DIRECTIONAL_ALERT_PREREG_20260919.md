# C1 lead-8 directional alert — preregistration

Issue #607. Parent #507 / #493 / #483 / #450.

## Objective

Combine the already accepted causal compression risk ranking with a zero-fit causal direction guess.

## Frozen risk input

Use authoritative #507 v2 scored T0-signal ledger and its prior-year-only compression score / B1..B5 bands unchanged.

Scored ledger SHA256:

`6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`

## Causal direction guess

At T0 signal bar k:

- ret8 = log(close[k]/close[k-8])
- if ret8>0, predict next C1 turn direction = TO_DOWN
- if ret8<0, predict next C1 turn direction = TO_UP
- ret8==0 -> direction abstention

No parameter is fitted.

## Research target

Using the same retrospective dense C1=S0-S1 oracle:

- event=1 iff at least one C1 slope-sign turn occurs in (k,k+8];
- if event=1, target direction = direction of the first such turn.

Target is evaluation-only.

## Outputs

For pooled 2018–2020 and each year:

1. actual turn count and turn-direction balance;
2. conditional direction accuracy among actual turns;
3. conditional direction accuracy by B1..B5;
4. joint correct-turn alert rate per band:
   P(turn within 8 AND predicted turn direction correct);
5. B5 vs B1 joint correct-alert risk difference and ratio;
6. fraction of T0 signals with nonzero ret8.

## Bootstrap

Use the same 20-trading-day calendar block definition as #507.

Bootstrap 5,000 block resamples, seed 20260919.

Report:

- 95% CI for pooled conditional direction accuracy;
- 95% CI for B5-B1 joint correct-alert rate difference.

## Directional-alert gate

`C1_LEAD8_DIRECTIONAL_ALERT_SUPPORTED` iff all are true:

1. pooled conditional direction accuracy among actual turns >0.60;
2. block-bootstrap 95% lower bound for conditional direction accuracy >0.55;
3. conditional direction accuracy >0.55 in at least 2 of 3 test years;
4. pooled B5 joint correct-alert rate > pooled B1 joint correct-alert rate;
5. block-bootstrap 95% lower bound for B5-B1 joint correct-alert rate difference >0.

Otherwise:

`C1_LEAD8_DIRECTIONAL_ALERT_NOT_SUPPORTED`.

## Boundary

No T0 PnL, route outcome or threshold search.

A positive result would establish a causal lead-8 C1 turn alert, not a trading rule.