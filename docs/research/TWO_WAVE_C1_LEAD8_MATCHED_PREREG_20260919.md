# C1 lead-8 matched-control precursor audit — preregistration

Issue #486. Parent #450. Discovery source #483.

## Objective

Test whether the precursor clues from #483 distinguish an imminent C1 slope turn from a non-imminent point inside the same final retrospective C1 slope segment.

## Oracle and matched clocks

Use the same final retrospective dense C1=S0-S1 slope-turn oracle as #483.

For every turn event t with enough preceding support:

- CASE = k8 = t-8
- CONTROL = k16 = t-16

Require that no oracle C1 slope turn occurs in (k16,t), so CASE and CONTROL belong to the same pre-turn C1 slope segment.

Thus:
- CASE means the turn occurs within the next 8 bars;
- CONTROL means no turn occurs within its next 8 bars.

The pair shares the same eventual turn direction and local C1 segment.

## Causal feature set

Reuse only features already registered in #483 and available at the respective clock.

Price-shape primary family:
- ret_4 / ret_8 / ret_16 / ret_32
- range_8 / range_16 / range_32
- rv_8 / rv_16 / rv_32
- efficiency_8 / efficiency_16 / efficiency_32

Structural family:
- last_base_g
- last_base_slope
- last_base_height
- last_base_duration
- previous_base_g
- base_same_sign_run
- latest causal S0/S1 segment slopes
- causal C1 residual-segment slope

Hazard/clock family reported separately:
- age_since_base_confirmation
- causal C1 age_ratio
- C1 evidence age
- S0/S1 evidence ages

No new feature is added after results are viewed.

## Paired feature test

For each continuous feature:

`Delta = feature(CASE) - feature(CONTROL)`.

For signed features, also report an oracle-direction-aligned diagnostic by multiplying by the eventual turn direction. This aligned diagnostic is discovery-only and cannot be used directly in a live rule.

Bootstrap:
- pair/event resampling
- 5,000 repetitions
- seed 20260919

A non-clock feature is marked `MATCHED_PRECURSOR_SUPPORTED` iff:
1. paired median Delta 95% CI excludes 0;
2. TO_UP and TO_DOWN point medians have the same sign;
3. at least 4 of 6 yearly point medians have the same sign.

Clock/hazard variables are never called morphology precursors merely for increasing with time.

## Simple directional rule family

At CASE k=t-8 only, for w in {8,16,32}:

`predicted turn direction = -sign(ret_w)`.

Exclude exact-zero returns.

Report:
- pooled accuracy
- balanced accuracy
- TO_UP recall
- TO_DOWN recall
- year-by-year accuracy

No window is selected post hoc.

A window is marked `DIRECTIONAL_CLUE` iff:
- pooled balanced accuracy >=0.55;
- at least 4/6 years accuracy >=0.52;
- both directional recalls >=0.52.

## Categorical paired outputs

Compare CASE vs CONTROL fractions for:
- last_base_relative
- causal C1 leg relative to eventual turn direction
- causal C1 descriptor
- causal C1 phase
- causal C1 residual-segment slope relative to eventual turn direction

Descriptive only.

## Boundaries

No PnL, route outcome, or trading rule selection.

This is still development discovery. Any actual causal predictor must be preregistered separately after this audit.
