# T0 retrospective C1×C2 nine-grid audit — preregistration

Issue #480. Parent #450.

## Objective

Revalidate the current T0/C1 rules and inspect the full retrospective C1×C2 three-state grid.

Questions:

1. Is C1 unsuitable as a direct direction supervisor for T0?
2. Does C1 opposition justify vetoing T0?
3. Is C1 RANGE materially safer than C1 OPPOSED?
4. What pattern appears across the full 3×3 C1×C2 grid?

This is a retrospective development audit. No causal/live claim.

## Source

- 000852.SH
- native 5m
- 2015–2020
- 70,114 rows
- SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

## Hierarchy

Use:

`continuity_hierarchy(base_inventory(bars), minimum=1, depth=3)`

- stage1 complete waves = C1
- stage2 complete waves = C2

At a T0 signal bar t, retrospective state uses the unique complete wave satisfying:

`start_bar <= t < end_bar`.

## Frozen three-state semantics

Use the existing wave direction field:

- UP if `g > +0.20`
- RANGE if `|g| <= 0.20`
- DOWN if `g < -0.20`

No threshold is retuned from T0 outcomes.

## T0 execution

Use:

`trend_shadow_trades(close, open, period=21, cost_bps_per_side=2.0)`

Only closed T0 trades are scored.

Outcome:

`net_log_return_proxy`.

## Absolute grid

Each eligible T0 trade receives:

- C1 absolute state: UP / RANGE / DOWN
- C2 absolute state: UP / RANGE / DOWN

Report all 9 cells.

Because long and short T0 trades have different alignment meaning, also report each absolute cell split by T0 side.

## T0-relative grid

Map each C1/C2 state relative to T0 trade side:

For T0 LONG:
- UP -> ALIGNED
- RANGE -> RANGE
- DOWN -> OPPOSED

For T0 SHORT:
- DOWN -> ALIGNED
- RANGE -> RANGE
- UP -> OPPOSED

Thus the relative grid is:

`C1 {ALIGNED,RANGE,OPPOSED} × C2 {ALIGNED,RANGE,OPPOSED}`.

This is the primary interpretive grid.

## Per-cell outputs

For every absolute and relative cell:

- N trades
- distinct C2 parent waves
- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration
- q10/q25/q75/q90 net bp
- parent-C2-wave cluster-bootstrap 95% CI for mean net bp when support permits

No minimum cell size is required for display.

Cells with fewer than 20 trades or 15 C2 parent waves are marked `DESCRIPTIVE_LOW_SUPPORT`.

## C1 aggregate groups

Pool over all C2 states:

- C1_ALIGNED
- C1_RANGE
- C1_OPPOSED

Report the same metrics and clustered mean CI.

### Gate V — C1 opposition veto

`C1_OPPOSED_RETROSPECTIVE_VETO_SUPPORTED` iff:

1. C1_OPPOSED has >=50 trades and >=30 C2 parent waves;
2. mean net bp <0;
3. parent-C2-wave cluster-bootstrap 95% upper bound for mean net bp <0;
4. both T0-LONG and T0-SHORT opposed subgroups have negative point-estimate mean.

Otherwise veto is not confirmed by this audit.

### Gate A — C1 aligned permission

`C1_ALIGNED_POSITIVE_BACKGROUND_SUPPORTED` iff:

1. >=50 trades and >=30 C2 parent waves;
2. mean net bp >0;
3. bootstrap 95% lower bound >0.

### Gate R — C1 RANGE permission

`C1_RANGE_NONNEGATIVE_BACKGROUND_SUPPORTED` iff:

1. >=30 trades and >=20 C2 parent waves;
2. mean net bp >0;
3. bootstrap 95% lower bound >=0.

If support is insufficient, report `C1_RANGE_INSUFFICIENT_SUPPORT`.

If the interval crosses zero, report `C1_RANGE_UNRESOLVED`.

## Direct-C1-supervision revalidation

For T0 trades whose retrospective C1 state is UP or DOWN:

- keep the exact T0 entry open and exit open;
- shadow side = +1 for C1 UP, -1 for C1 DOWN;
- same 4bp completed-trade proxy cost;
- compare shadow-C1-direction net result to actual T0 net result.

This tests only:

> should C1 replace T0's direction over a T0 opportunity?

It is not a C1 own-lifecycle strategy.

Report:

- shadow-C1 mean net bp
- actual-T0 mean net bp on the same rows
- paired difference `shadow_C1 - actual_T0`
- 5,000 C2-parent-wave cluster-bootstrap 95% CI for paired mean difference
- shadow-C1 win rate.

`C1_DIRECT_SUPERVISION_REJECTED` iff paired mean difference <0 and its bootstrap 95% upper bound <0.

## Nine-grid interpretation boundary

The 9 cells are descriptive.

This study may confirm the predeclared C1 rules above, but it may not create a new nine-cell router by selecting favorable cells after seeing their outcomes.

If the grid shows a coherent pattern worth using, it must become a separate preregistered rule study.

## Bootstrap

- cluster unit: retrospective C2 parent complete wave
- 5,000 resamples
- seed 20260919
- all T0 trades in a sampled C2 wave travel together.

## Authority

Consumed development evidence only.

No causal signal/router/live/trade/production authority.
