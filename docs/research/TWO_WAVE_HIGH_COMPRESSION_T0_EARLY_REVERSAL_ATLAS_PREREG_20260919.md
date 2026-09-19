# High-compression T0 early-reversal precursor atlas — preregistration

Issue #543. Parent #540 / #537 / #507 / #450.

## Frozen universe

Use #507 strict walk-forward T0 signals with risk_band in {4,5}.

Expected support from #540:
- N=356 high-risk signals
- EARLY_REVERSAL=45
- SURVIVES_8=311.

Label:
- EARLY_REVERSAL iff original T0 exit_bar <= signal_bar+9
- otherwise SURVIVES_8.

## Causal decision clock

All features are evaluated at the T0 signal close k and may use only bars/nodes known by k.

## Continuous feature families

### T0 breakout geometry
- breakout_excess: side-aligned log distance beyond prior 21-bar close extreme

### Raw path aligned to T0 side
- ret_aligned_4
- ret_aligned_8
- ret_aligned_16
- ret_aligned_32

### Unsigned path activity
- range_8 / range_16 / range_32
- rv_8 / rv_16 / rv_32
- efficiency_8 / efficiency_16 / efficiency_32

### Frozen #507 compression components
- compression_score
- risk_abs_ret_8
- risk_range_8
- risk_rv_8
- risk_efficiency_8

### Latest confirmed base-wave features
- base_g_aligned_to_T0
- base_slope_aligned_to_T0
- base_height
- base_duration
- age_since_base_confirmation
- base_same_sign_run

### Causal C1 state features
- c1_age_ratio
- c1_period
- c1_amplitude
- c1_evidence_age

### Latest confirmed segment slopes
- s0_seg_slope_aligned_to_T0
- s1_seg_slope_aligned_to_T0
- c1_segment_residual_slope_aligned_to_T0
- s0_evidence_age
- s1_evidence_age.

## Categorical features

- T0 side LONG/SHORT
- risk band B4/B5
- latest base direction relative to T0: ALIGNED/RANGE/OPPOSED
- causal C1 leg relative to T0: ALIGNED/OPPOSED/UNRESOLVED
- causal C1 descriptor relative to T0: ALIGNED/RANGE/OPPOSED/UNRESOLVED
- causal C1 phase EARLY/MIDDLE/LATE/UNRESOLVED.

## Continuous atlas outputs

For every continuous feature:
- EARLY_REVERSAL N/median/q25/q75
- SURVIVES_8 N/median/q25/q75
- median difference EARLY-SURVIVES
- 20-trading-day calendar-block bootstrap 95% CI for median difference, 5000 reps, seed 20260919
- univariate ROC AUC for EARLY_REVERSAL using raw feature orientation
- yearly median difference for 2018/2019/2020.

`EARLY_REVERSAL_CLUE` iff:
1. bootstrap 95% CI for median difference excludes 0;
2. at least 2 of 3 yearly median differences have the same sign as pooled;
3. abs(AUC-0.5) >= 0.05.

This is a clue gate, not a production-feature gate.

## Categorical atlas outputs

For every category value:
- N
- EARLY_REVERSAL count/rate
- lift versus pooled high-risk early-reversal rate.

Values with N<20 are marked LOW_SUPPORT.

## Boundary

No classifier, no threshold, no T0 PnL optimization.

A clue may only advance to a separately preregistered causal classifier/rule study.