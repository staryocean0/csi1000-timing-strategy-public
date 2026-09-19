# C1 lead-8 precursor atlas — preregistration

Issue #483. Parent #450.

## Objective

Use the final retrospective C1 bandpass slope-turn process as an oracle, then search for patterns that are already visible at least 8 native 5m bars before the turn.

This is a precursor-discovery study, not a trading rule.

## Oracle

Use the accepted continuity hierarchy:

- S0 = stage1 input stream
- S1 = stage2 input stream
- C1 = log(S0)-log(S1)

On the common occurrence support, interpolate log(S0), log(S1) linearly and define native retrospective slope:

`dC1(t)=C1(t)-C1(t-1)`

A turn event at bar t occurs when:

- `sign(dC1(t)) != sign(dC1(t-1))`
- both signs are nonzero

Direction:

- TO_UP if `dC1(t)>0`
- TO_DOWN if `dC1(t)<0`

This oracle is retrospective and may use future-confirmed nodes.

## Lead clocks

For every oracle turn t, observe causal features at:

- k=t-32
- k=t-16
- k=t-8

Only information with knowledge time <=k is allowed.

The final path `[t-8,t)` is separately summarized as mechanism-only evidence and is explicitly forbidden as a lead-8 predictor.

## Causal feature families

### Raw path features ending at k

Signed:

- ret_4, ret_8, ret_16, ret_32 = log close[k]/close[k-w]

Unsigned:

- range_8, range_16, range_32 = log(max high / min low)
- rv_8, rv_16, rv_32 = std of one-bar log close returns
- efficiency_8, efficiency_16, efficiency_32 = abs(net log move) / total absolute log-return variation

### Latest confirmed base/T0-wave features

Using only base waves with `known_from_bar<=k`:

- last_base_g
- last_base_slope_per_bar
- last_base_height
- last_base_duration
- last_base_direction
- age_since_last_base_confirmation
- previous_base_g
- last_two_base_same_sign
- same-sign run length of completed base-wave g sign

### Causal C1 hierarchy state

Using stage1 causal state at k:

- status
- causal leg direction
- latest completed-wave descriptor UP/RANGE/DOWN
- phase EARLY/MIDDLE/LATE
- age_ratio
- period
- amplitude
- evidence_age_bars

### Latest confirmed segment slopes

For S0 and S1 separately, using only nodes with `known_from_bar<=k`:

- latest confirmed segment log slope per occurrence bar
- evidence age of latest segment endpoint

Derived causal residual slope proxy:

`c1_segment_residual_slope = slope(S0)-slope(S1)`

This is causal and is not the final retrospective dC1 oracle.

## Direction-aligned event study

For signed features, define an oracle-direction aligned version:

- multiply by +1 for TO_UP
- multiply by -1 for TO_DOWN

This is used only to discover symmetric precursor structure.

It is not itself an operational feature because future turn direction is unknown at decision time.

## Primary precursor contrasts

For each event and each continuous causal feature:

1. level at lead 32 / 16 / 8
2. paired change:
   - lead8 minus lead16
   - lead8 minus lead32

For signed features, use direction-aligned values.

Cluster unit is the turn event.

Bootstrap 5,000 event resamples, seed 20260919.

A continuous feature is marked `PRECURSOR_CLUE` only if:

- the paired lead8-minus-lead16 median has a bootstrap 95% interval excluding 0 in the same direction for the pooled aligned event study;
- at least 4 of 6 yearly point medians have the same sign;
- the effect is not driven solely by one turn direction: TO_UP and TO_DOWN aligned point medians have the same sign.

This is a clue criterion, not a model-acceptance gate.

## Categorical precursor outputs

At lead 32 / 16 / 8 report distributions for:

- last_base_direction
- last_two_base_same_sign
- causal C1 leg relative to future turn direction
- causal C1 descriptor
- causal C1 phase
- sign of causal C1 residual segment slope proxy relative to future turn direction

Report transition in probability from lead16 to lead8.

No categorical state is promoted to a rule in this pass.

## Mechanism-only last-8-bar panel

For each turn direction, summarize over `[t-8,t)`:

- net raw return
- realized range
- realized variation
- number of base-wave confirmations

This panel is explanatory only and must never be described as available at t-8.

## Boundaries

No T0/C1 PnL or route outcome is used for feature selection.

No causal predictor, signal, router or production authority is created by this atlas.
