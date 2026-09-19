# C2/C3 lowpass-vs-bandpass representation fork — Pass A preregistration

Issue #463. Parent #450.

## Purpose

Before continuing R2b, compare two candidate trend-state representations without any T0/C1 execution outcome.

### Bandpass pair

- BP2 = C2 = S1 - S2
- BP3 = C3 = S2 - S3

This isolates each adjacent-scale residual.

### Lowpass pair

- LP2 = S1 = BP2 + LP3
- LP3 = S2 = BP3 + S3

This keeps the cumulative slower trend background from each scale downward.

The names LP2/LP3 in this audit are explicit aliases to avoid ambiguity.

## Frozen source

- 000852.SH
- native 5m
- 2015–2020 development
- 70,114 rows
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Use scale-specific continuity depth 4.

## Pass-A outputs for both representations

### 1. Support and determinism

- joint support bars / source fraction
- finite rows
- deterministic replay
- no extrapolation

### 2. Native-slope trend persistence

For each component:

- positive / negative run counts
- median, q25/q75/q90/q95/max run length
- turn count
- turn-spacing median/q25/q75/q90

For the two-component relation:

- ++ / +- / -+ / -- occupancy
- relation-state run lengths

### 3. Scale separation

Compare slower/faster turn-spacing median ratio.

A candidate must preserve a recognizable slower/faster hierarchy.

### 4. Correlation

- level zero-lag Pearson correlation
- native-slope zero-lag Pearson correlation

Correlation is descriptive only. Lower correlation is not automatically better.

### 5. Year stability

For each year 2015–2020:

- four relation-state fractions
- component turn counts
- turn-spacing median
- level/slope correlation

Summary drift metrics:

- maximum minus minimum yearly fraction for each relation state
- mean absolute deviation of yearly relation fractions from pooled fractions
- coefficient of variation of annual turn-spacing medians when finite

### 6. Exact causal observability

Using final-node bracketing clocks:

Bandpass:
- BP2 slope requires S1 and S2
- BP3 slope requires S2 and S3
- joint requires S1/S2/S3

Lowpass:
- LP2 slope requires S1 only
- LP3 slope requires S2 only
- joint requires S1/S2

Report delay q25/q50/q75/q90/q95/q99 and availability within:
0/4/8/16/32/64/128/256/512 bars.

## Early discrimination rule

No weighted score.

A representation may be declared an **EARLY_PREFERRED_TARGET** only if all are true:

1. joint support >=90%;
2. deterministic representation;
3. slower/faster median turn-spacing ratio remains between 2 and 6;
4. it is no worse at q25/q50/q75/q90 exact joint delay and is strictly better at at least three of those four quantiles;
5. its mean absolute yearly relation-fraction drift is no more than 110% of the alternative;
6. its pooled median relation-run length is no less than 80% of the alternative.

If neither representation meets this one-sided Pareto-style rule, verdict is:

`NO_EARLY_WINNER__ADVANCE_BP_AND_LP_IN_PARALLEL`.

This does not mean the two are equivalent. It means trend-state utility cannot yet be resolved without later causal-carrier and execution-routing evidence.

## Forbidden

Pass A cannot read:

- T0 outcome
- C1 outcome
- PnL
- route winner
- future return
- execution-arm labels

No routing rule, state threshold or production authority.
