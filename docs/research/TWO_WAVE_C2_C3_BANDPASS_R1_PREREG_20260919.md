# R1 — C2/C3 bandpass morphology atlas preregistration

Issue #455. Parent #450. R0 #452 passed.

## Objective

Describe the intrinsic retrospective morphology of the frozen explicit bandpass residuals:

- C2 = S1-S2
- C3 = S2-S3

before any T0/C1 execution outcome is visible.

R1 is descriptive. It does not create a router.

## Input

Use the R0 frozen joint-support representation only.

Frozen source:

- 000852.SH
- native 5m
- 2015–2020 development
- source SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Frozen R0 joint ledger SHA256:

`0e632a2b782194f8d5d433ffd019780845de8f1d0b8a3e12124351073008e3ec`

## Native slopes

For each residual:

`dCk(t)=Ck(t)-Ck(t-1)`.

No deadband is introduced in R1.

Slope sign is:

- + if dCk>0
- - if dCk<0
- 0 only for exact zero

Exact-zero rows are reported separately and excluded from sign-run calculations.

## Required atlas outputs

### 1. Level distributions

For C2 and C3 overall and by year:

- mean
- std
- q01/q05/q25/q50/q75/q95/q99
- min/max

### 2. Native-slope distributions

For dC2 and dC3 overall and by year:

- same summary quantiles
- median absolute slope
- RMS slope

### 3. Slope-sign relation occupancy

For rows where both slopes are nonzero:

- ++
- +-
- -+
- --

Report counts and fractions overall and by year.

### 4. Relation-state run lengths

Consecutive native-bar runs of each of the four sign relations.

Report:

- run count
- q10/q25/median/q75/q90/q95/max length

### 5. Individual slope-sign runs

For C2 and C3 separately:

- positive-run lengths
- negative-run lengths
- turn count
- turn spacing

### 6. Turn lead/lag

For every C2 slope-sign turn, find the nearest C3 slope-sign turn in occurrence time; and vice versa.

Report signed nearest-turn lag and absolute lag quantiles.

This is retrospective descriptive timing only.

### 7. Correlation atlas

Report:

- zero-lag Pearson correlation of C2 and C3 levels
- zero-lag Pearson correlation of dC2 and dC3
- lag correlation for levels at integer lags -2048..+2048
- lag correlation for slopes at integer lags -2048..+2048
- best absolute correlation and corresponding lag

Lag sign convention:

positive lag L means C3 is shifted later relative to C2 when correlating C2(t) with C3(t+L).

Best-lag diagnostics do not establish causality.

### 8. Scale ratios

Overall and by year:

- std(C3)/std(C2)
- RMS(dC3)/RMS(dC2)
- median(|dC3|)/median(|dC2|)

### 9. Year stability

For 2015–2020 report:

- four sign-relation fractions
- level correlation
- slope correlation
- turn counts
- scale ratios

## No selection rule

R1 does not rank or accept any relationship state.

No threshold, cell, lag, sign pattern or phase may be promoted based on R1 alone.

## Forbidden

R1 may not read or join:

- T0 outcomes
- C1 outcomes
- PnL
- route winners
- future return
- execution-arm labels

## Next gate

R2 causal observability may only inspect R1 variables after R1 is frozen.

No R1 clue becomes a router input until it passes R2.
