# C1 causal-leg × compression state atlas — preregistration

Issue #584. Parent #579 / #577 / #507 / #450.

## Universe

Authoritative #507 v2 T0 signal bars, 2018–2020.

## Current causal state

At each T0 signal bar k, compute stage1 causal_state using only hierarchy information known by k.

Map causal C1 leg relative to current T0 side:
- ALIGNED
- OPPOSED
- UNRESOLVED.

Reuse authoritative #507 v2 risk_band B1..B5 exactly.

## Future retrospective target

Within (k,k+8], use the first frozen retrospective C1=S0-S1 slope-sign turn:
- NO_TURN
- FAVORABLE_TURN if new direction == T0 side
- ADVERSE_TURN if new direction != T0 side.

## Outputs

For every causal-leg-state × B1..B5 cell:
- N
- any-turn rate
- adverse-turn rate
- favorable-turn rate
- adverse share among turns
- among turn events: fraction future turn direction == current causal C1 leg.

Also report pooled by causal-leg state and pooled by risk band, plus year splits.

## Boundary

Descriptive atlas only.
No PnL, no post-hoc cell routing rule, no signal/trade authority.