# Strong-C2 override audit — preregistration

Issue #477. Parent #450. Structural premise from #473.

## Objective

Test the economic interpretation of the structural pace-dominance result:

> When C2 is in a strong directional bandpass leg, a T0 trade aligned with C2 should remain positively controlled by C2 even if the adjacent C1 leg points the other way.

This is a retrospective development audit.

It does not create a causal/live rule.

## Frozen source

- 000852.SH
- native 5m
- 2015–2020 development
- source SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

## Frozen hierarchy and leg geometry

Use:

`continuity_hierarchy(base_inventory(bars), minimum=1, depth=3)`

- stage1 waves = C1
- stage2 waves = C2

Retrospective leg direction for a complete wave:

- UP on `start_bar <= t <= high_bar`
- DOWN on `high_bar < t < end_bar`

Shared terminal low uses the next wave via left-closed/right-open wave assignment.

Leg pace:

- UP: `height_log / (high-start)`
- DOWN: `height_log / (end-high)`

## Strong-C2 bucket

Within C2 leg direction separately:

- compute empirical pace percentile across all complete C2 legs;
- `STRONG_C2` iff percentile >0.75.

This is identical to the #473 strong-parent definition.

No return/PnL is used to define the bucket.

## C1 state at T0 signal time

At each eligible T0 signal bar, locate the retrospective C1 complete-wave leg containing that bar.

C1 relation:

- `C1_ALIGNED` if C1 leg direction == C2 leg direction == T0 trade side
- `C1_OPPOSED` if C1 leg direction != C2 leg direction

C1 leg pace percentile is computed within C1 direction separately.

`STRONG_OPPOSING_C1` means:

- C1_OPPOSED
- C1 leg pace percentile >0.75

This is the predeclared hardest counterexample bucket.

## T0 execution module

Use the existing frozen T0 research comparator:

`trend_shadow_trades(close, open, period=21, cost_bps_per_side=2.0)`

Properties:

- signal on close breakout
- fill next raw open
- own T0 lifecycle until next T0 reversal
- 4bp round-trip proxy cost for a completed trade
- only closed trades are scored

No fixed-window C1 shadow arm is used.

## Primary universe

A closed T0 trade is eligible iff:

1. signal bar is inside a complete retrospective C2 leg;
2. that C2 leg is STRONG_C2;
3. T0 trade side aligns with the C2 leg direction;
4. a retrospective C1 leg is available at the same signal bar.

The outcome is the trade's own `net_log_return_proxy`.

## Primary estimands

For each C1 relation group:

- trade count
- parent C2-wave count
- mean net bp
- median net bp
- win rate
- q10/q25/q75/q90 net bp
- fast-loss rate
- mean duration

Primary groups:

- C1_ALIGNED
- C1_OPPOSED

Hard-counterexample group:

- STRONG_OPPOSING_C1

Also report pooled, C2-UP and C2-DOWN separately.

## Dependence / bootstrap

Inferential cluster = complete C2 parent wave.

Bootstrap:

- 5,000 parent-wave cluster resamples
- seed 20260919
- resample C2 parent-wave ids with replacement
- all eligible T0 trades belonging to sampled parent waves travel together

For each group, bootstrap:

- mean net bp
- win rate

For aligned-vs-opposed comparison bootstrap:

`Delta = mean_net_bp(OPPOSED) - mean_net_bp(ALIGNED)`

## Gate A — sign override

`STRONG_C2_SIGN_OVERRIDE_SUPPORTED` iff:

1. pooled C1_OPPOSED has at least 50 trades and at least 30 distinct C2 parent waves;
2. pooled C1_OPPOSED mean net bp >0;
3. cluster-bootstrap 95% lower bound for opposed mean net bp >0;
4. UP and DOWN opposed subgroups each have positive point-estimate mean net bp.

This directly tests:

> opposing C1 does not flip the aggregate strong-C2-aligned T0 result negative.

## Gate B — hard counterexample

`STRONG_C2_SURVIVES_STRONG_OPPOSING_C1` iff:

1. STRONG_OPPOSING_C1 has at least 30 trades and at least 20 distinct C2 parent waves;
2. mean net bp >0;
3. cluster-bootstrap 95% lower bound for mean net bp >0.

If support is smaller, verdict is `HARD_COUNTEREXAMPLE_INSUFFICIENT_SUPPORT`, not failure.

## Gate C — veto removal

A stronger conclusion that C1 should lose veto authority requires all Gate-A conditions plus:

1. aligned-group mean net bp >0;
2. opposed-group mean net bp is at least 50% of aligned-group mean net bp;
3. bootstrap 95% lower bound for the retention ratio
   `mean(OPPOSED)/mean(ALIGNED)`
   is >=0.50, computed only in bootstrap draws where aligned mean >0;
4. no C2-UP or C2-DOWN opposed subgroup has negative point-estimate mean.

Verdict:

`STRONG_C2_C1_VETO_REMOVAL_SUPPORTED`

The 50% retention threshold is frozen before outcomes are inspected.

## Final verdict hierarchy

1. `STRONG_C2_C1_VETO_REMOVAL_SUPPORTED`
2. `STRONG_C2_SIGN_OVERRIDE_SUPPORTED_BUT_C1_STILL_MATERIAL`
3. `STRONG_C2_SIGN_OVERRIDE_NOT_SUPPORTED`

Hard-counterexample status is reported separately.

## Interpretation boundary

This study is retrospective because C2/C1 leg identity and strength use complete-wave morphology.

Even a positive result does not authorize a live route.

A subsequent causal study must determine whether strong-C2 pace dominance can be recognized early enough.

No paper/live/trade/production authority.
