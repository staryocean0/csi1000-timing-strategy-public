# C1 harmful-vs-helpful turn ranking for T0 — preregistration

Issue #589. Parent #507 / #493 / #450.

## Objective

Separate C1 turns within the next 8 native bars into turns that are harmful or helpful to the current T0 trade side, using only causal information at the T0 signal bar.

## Frozen decision universe

Use the authoritative #507 v2 walk-forward scored T0 signal ledger for 2018-2020 only.

Reconstruct T0 side from the frozen period-21 own-lifecycle breakout engine by exact signal_bar join.

Compute signed ret_8 from raw closes through the signal bar only.

## Retrospective research target

Use the same final dense C1=S0-S1 native-slope turn oracle.

For each T0 signal bar k:
- if no C1 turn occurs in (k,k+8], target=NO_TURN;
- if the post-turn C1 slope sign equals T0 side, target=HELPFUL_TURN;
- if the post-turn C1 slope sign opposes T0 side, target=HARMFUL_TURN.

If more than one turn occurs in the horizon, use the first turn and report multi-turn count. The prior oracle has minimum observed turn spacing of 8 bars, so multi-turn support is expected to be negligible.

## Causal direction proxy

For nonzero ret_8:

predicted post-turn direction = -sign(ret_8).

This is motivated by prior mechanism evidence but receives a fresh 2018-2020 test here.

Direction-proxy gate:
1. at least 100 actual turn events;
2. accuracy >0.55;
3. 20-trading-day block-bootstrap 95% lower bound for accuracy >0.50;
4. yearly accuracy >0.50 in at least 2 of 3 years.

## Signed turn score

Define relation:
- +1 if sign(ret_8) equals T0 side;
- -1 if sign(ret_8) opposes T0 side;
- 0 if ret_8 is exactly zero.

signed_turn_score = compression_score × relation.

Positive high score means predicted harmful-turn risk.
Negative high-magnitude score means predicted helpful-turn risk.

## Primary outputs

Report:
- harmful-turn rate and helpful-turn rate for relation=+1 and relation=-1;
- 2×5 table: ret8 relation to T0 × frozen #507 compression band B1..B5;
- AUC of signed_turn_score for HARMFUL_TURN vs all other signals;
- AUC of -signed_turn_score for HELPFUL_TURN vs all other signals;
- year-by-year results.

## Paired directional-risk gates

Harmful separation passes iff:
- harmful-turn rate(relation=+1) > harmful-turn rate(relation=-1);
- 20-trading-day block-bootstrap 95% lower bound for the difference >0.

Helpful separation passes iff:
- helpful-turn rate(relation=-1) > helpful-turn rate(relation=+1);
- 20-trading-day block-bootstrap 95% lower bound for the difference >0.

## Final verdict

C1_DIRECTIONAL_TURN_RISK_SUPPORTED iff:
1. direction-proxy gate passes;
2. harmful separation passes;
3. helpful separation passes;
4. harmful AUC >0.52;
5. helpful AUC >0.52.

Otherwise C1_DIRECTIONAL_TURN_RISK_NOT_SUPPORTED.

## Boundary

No T0 PnL or routing outcome is used.

A positive result would establish a causal harmful/helpful turn-risk representation, not a trading veto.