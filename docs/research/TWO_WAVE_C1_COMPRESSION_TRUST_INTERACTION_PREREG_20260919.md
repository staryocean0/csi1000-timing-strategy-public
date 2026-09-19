# C1 compression-risk trust interaction — preregistration

Issue #599. Parent #507 / #493 / #450.

## Objective

Test whether causal lead-8 compression risk modifies the reliability of the currently observable C1 leg direction for T0.

## Frozen inputs

1. Authoritative #507 v2 walk-forward scored T0 signal bars.
2. Then-known causal C1 leg from the accepted scale-specific continuity carrier at the same T0 signal bar.
3. T0 own-lifecycle net outcome from the frozen period-21 breakout engine.

## Compression groups

- LOW = B1+B2
- MID = B3
- HIGH = B4+B5

These groupings are frozen before viewing T0 outcome by interaction cell.

## C1 relation

At signal bar k:

- ALIGNED if causal C1 leg direction == T0 trade side
- OPPOSED otherwise

No retrospective C1 label is used in the interaction state.

## Primary cells

Report N, mean/median net bp, win rate, fast-loss rate and duration for:

- LOW × ALIGNED
- LOW × OPPOSED
- MID × ALIGNED
- MID × OPPOSED
- HIGH × ALIGNED
- HIGH × OPPOSED

Also report B1..B5 × causal-C1 relation descriptively.

## Primary interaction estimand

Spread_LOW = mean_net(ALIGNED,LOW) - mean_net(OPPOSED,LOW)

Spread_HIGH = mean_net(ALIGNED,HIGH) - mean_net(OPPOSED,HIGH)

Interaction = Spread_HIGH - Spread_LOW.

Compression-as-C1-trust-decay predicts Interaction < 0.

## Directional mechanism checks

Aligned degradation:

mean_net(ALIGNED,HIGH) - mean_net(ALIGNED,LOW) < 0.

Opposed relief:

mean_net(OPPOSED,HIGH) - mean_net(OPPOSED,LOW) > 0.

## Bootstrap

Use 20-trading-day calendar blocks of scored T0 signal bars.

5,000 resamples, seed 20260919.

Report 95% CI for:

- Interaction
- aligned degradation
- opposed relief

## Support gates

Each of the four primary LOW/HIGH × ALIGNED/OPPOSED cells must have:

- at least 50 trades
- at least 20 calendar blocks with representation

otherwise final mechanism verdict is INSUFFICIENT_SUPPORT.

## Acceptance

C1_COMPRESSION_TRUST_DECAY_SUPPORTED iff:

1. all four primary cells meet support;
2. point Interaction <0;
3. bootstrap 95% upper bound for Interaction <0;
4. aligned degradation point <0;
5. opposed relief point >0;
6. at least 2 of 3 test years have Interaction <0.

Directional sub-contrast confidence intervals are reported but are not separate hard gates.

Otherwise:

C1_COMPRESSION_TRUST_DECAY_NOT_SUPPORTED.

## Boundary

This study may use T0 outcome because #507 score construction is already frozen and PnL-blind.

A positive result would justify compression risk as a causal trust modifier for C1, not yet a production veto/entry rule.