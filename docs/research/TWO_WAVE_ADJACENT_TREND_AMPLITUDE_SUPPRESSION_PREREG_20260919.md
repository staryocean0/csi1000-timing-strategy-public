# Adjacent-scale trend suppression audit — preregistration

Issue #473. Parent #450.

## Objective

Test the structural hypothesis:

> When a slower adjacent bandpass leg is strong, the faster child band either has smaller intrinsic detrended amplitude, or becomes small relative to the slower parent's unit-time trend advance.

Pairs:

1. C2 parent leg -> C1 child-wave amplitude
2. C3 parent leg -> C2 child-wave amplitude

No T0/C1 outcome, PnL, route label or future-return target is used.

## Hierarchy

Use the frozen scale-specific continuity hierarchy:

`continuity_hierarchy(base_inventory(bars), minimum=1, depth=3)`

- stage1 waves = C1
- stage2 waves = C2
- stage3 waves = C3

Frozen source:

- 000852.SH
- native 5m
- 2015–2020 development
- 70,114 rows
- SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

## Parent bandpass leg strength

For each complete parent low-high-low wave:

UP leg:

`pace_up = height_log / (high_bar-start_bar)`

DOWN leg:

`pace_down = height_log / (end_bar-high_bar)`

where `height_log` is the parent wave's detrended residual height above its low-to-low baseline.

This is the frozen interpretation of the user's "bandpass unit-time slope".

The parent's low-to-low baseline migration `s` is NOT the primary strength variable.

## Child eligibility

A child complete wave belongs to a parent leg only when its full occurrence interval is contained inside the leg:

UP:
`parent.start_bar <= child.start_bar < child.end_bar <= parent.high_bar`

DOWN:
`parent.high_bar <= child.start_bar < child.end_bar <= parent.end_bar`

Child waves crossing the parent turn are excluded from that leg.

## Primary child intrinsic amplitude

For each eligible child wave:

`A_child = child.height_log`

This is the detrended residual peak above the child's own low-to-low baseline.

It implements the user's rotated-coordinate idea by flattening/removing the child baseline without introducing an arbitrary time-vs-price Euclidean scale.

Child intrinsic amplitude pace:

`P_child = A_child / child.duration`

## Orthogonal-distance robustness amplitude

Because literal Euclidean perpendicular distance depends on the relative scaling of time and log-price axes, it is not used as the primary amplitude.

As a robustness check, define for each child level a fixed scale:

`A_ref = median(A_child)`

over all eligible child waves at that level.

With normalized time `tau=(t-start)/duration` and vertical scale `A_ref`, the projected orthogonal amplitude in log-price units is:

`A_orth = A_child / sqrt(1 + (DeltaLow/A_ref)^2)`

where:

`DeltaLow = log(end_low/start_low)`.

This scale is fixed once per child level and never outcome-selected.

## Parent-leg aggregation

The inferential unit is the parent complete wave.

For each parent leg with at least one eligible child, record:

- parent wave id
- direction UP/DOWN
- leg pace
- child count
- median child A_child
- median child A_orth
- median child P_child
- pace dominance ratio:

`D = parent_leg_pace / median(P_child)`

## Strength ranking

Within each parent level and leg direction separately, convert leg pace to its empirical percentile rank.

This avoids confounding UP/DOWN legs merely because their duration distributions differ.

Strong leg:

- strength percentile > 0.75

Weak leg:

- strength percentile <= 0.25

No other threshold is searched.

## Hypothesis A — absolute child-amplitude suppression

For each pair separately:

1. Spearman correlation between parent-leg strength percentile and median child `A_child` must be negative.
2. Parent-wave cluster bootstrap, 5,000 replicates, seed 20260919:
   - 95% CI upper bound for Spearman rho < 0.
3. Strong-vs-weak median log-amplitude difference:

`median(log A_child | strong) - median(log A_child | weak)`

must be negative with bootstrap 95% CI upper bound < 0.

The same direction must hold for `A_orth`; orthogonal robustness is reported but is not an independent significance gate.

`ABSOLUTE_CHILD_AMPLITUDE_SUPPRESSION_SUPPORTED` requires the primary A_child gates to pass for BOTH C2->C1 and C3->C2.

## Hypothesis B — relative parent-trend dominance

For each parent leg:

`D = parent_leg_pace / median(child amplitude pace)`.

For strong legs, report:

- median D
- fraction of legs with D>1

Cluster bootstrap, 5,000 replicates.

Pair-level support requires BOTH:

1. bootstrap 95% lower bound for median D > 1;
2. bootstrap 95% lower bound for fraction(D>1) > 0.50.

`RELATIVE_PARENT_TREND_DOMINANCE_SUPPORTED` requires both C2->C1 and C3->C2 to pass.

## Direction robustness

UP and DOWN legs are reported separately for:

- rho
- strong/weak amplitude contrast
- strong-leg median D
- strong-leg fraction D>1

Because C3 has only 39 complete waves, direction-specific cells are descriptive robustness outputs and are not hard gates.

## Final verdict

- `FULL_ADJACENT_TREND_SUPPRESSION_SUPPORTED`
  - absolute suppression passes both pairs
  - relative parent dominance passes both pairs

- `RELATIVE_DOMINANCE_ONLY__ABSOLUTE_SUPPRESSION_NOT_ESTABLISHED`
  - relative parent dominance passes both pairs
  - absolute suppression does not pass both pairs

- `ADJACENT_TREND_SUPPRESSION_NOT_SUPPORTED`
  - relative parent dominance fails at least one pair

## Interpretation boundary

Even a positive result does not directly authorize T0/C1 routing.

It would justify a simpler state-machine hypothesis:

- strong C2 leg may allow C1 interference to be ignored when considering T0;
- strong C3 leg may allow C2 interference to be ignored when considering C1.

A routing rule would still require a separately preregistered causal study.

No production/paper/live authority.
