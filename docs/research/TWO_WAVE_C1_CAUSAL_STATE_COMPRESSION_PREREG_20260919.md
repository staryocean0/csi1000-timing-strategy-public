# Causal C1-state × compression map — preregistration

Issue #594. Parent #589 / #507 / #450.

## Objective

Test whether the then-known causal C1 current leg supplies the missing directional state for the already validated #507 compression turn-risk score.

## Universe

Use authoritative #507 v2 walk-forward scored T0 signal bars for 2018-2020.

## Causal C1 state

Build the accepted continuity hierarchy and prepare stage1 as-of state.

At T0 signal bar k use `causal_state(prepared_stage1,k)` only.

If RESOLVED:
- C1 leg UP/DOWN is mapped relative to T0 side;
- same direction = ALIGNED;
- opposite direction = OPPOSED.

UNRESOLVED is reported but excluded from the two primary branch tests.

## Target

Reuse #589 first-turn target in (k,k+8]:
- HARMFUL_TURN if post-turn C1 slope sign opposes T0 side;
- HELPFUL_TURN if post-turn sign aligns with T0 side;
- NO_TURN if no C1 turn.

## Primary map

2 × 5 table:
- rows: causal C1 relation ALIGNED / OPPOSED;
- columns: frozen #507 risk bands B1..B5;
- cells report N, harmful-turn rate, helpful-turn rate, any-turn rate.

## ALIGNED branch gate

Within causal C1 ALIGNED:
1. N >=200;
2. harmful-turn rate B5 > B1;
3. 20-trading-day block-bootstrap 95% lower bound for B5-B1 harmful-risk difference >0;
4. band harmful-rate Spearman rho >=0.50;
5. continuous compression_score AUC for HARMFUL_TURN >0.52;
6. B5>B1 in at least 2 of 3 test years.

## OPPOSED branch gate

Within causal C1 OPPOSED:
1. N >=200;
2. helpful-turn rate B5 > B1;
3. 20-trading-day block-bootstrap 95% lower bound for B5-B1 helpful-risk difference >0;
4. band helpful-rate Spearman rho >=0.50;
5. continuous compression_score AUC for HELPFUL_TURN >0.52;
6. B5>B1 in at least 2 of 3 test years.

## Coverage gate

Resolved causal-C1 coverage on the 945 authoritative scored signals must be >=95%.

## Final verdict

`C1_CAUSAL_STATE_COMPRESSION_DIRECTIONAL_MAP_SUPPORTED` iff coverage and both branch gates pass.

Otherwise:

`C1_CAUSAL_STATE_COMPRESSION_DIRECTIONAL_MAP_NOT_SUPPORTED`.

## Boundary

No T0 PnL or routing outcome.

A positive result establishes a causal directional turn-risk map only.