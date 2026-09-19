# R1 — C2/C3 bandpass morphology atlas result

Issue #455. Parent #450.

## Verdict

`R1_BANDPASS_MORPHOLOGY_ATLAS_COMPLETE`

This is a retrospective intrinsic morphology atlas only. No T0/C1 outcome, PnL, route winner or future return was used.

## Frozen input

R0 joint C2/C3 bandpass ledger SHA256:

`0e632a2b782194f8d5d433ffd019780845de8f1d0b8a3e12124351073008e3ec`

Rows: 68,911.

## 1. Scale structure

C2 native-slope turns:

- turns: 381
- turn-spacing median: 157.5 native 5m bars
- q25/q75: 90 / 238.5
- mean: 180.1

C3 native-slope turns:

- turns: 97
- turn-spacing median: 569.5 bars
- q25/q75: 301.75 / 921.25
- mean: 676.25

Median turn-spacing ratio:

`C3 / C2 = 3.6159`.

This independently reproduces the adjacent-scale ~3–4x structure without using outcomes.

Additional structural check:

- shared C2/C3 slope-turn bars: 87
- 89.69% of C3 turns coincide with a C2 turn
- 22.83% of C2 turns coincide with a C3 turn

Thus the slower C3 turning structure is mostly nested inside the denser C2 turn process.

## 2. Amplitude / pace relation

Level standard deviation:

- C2: 0.0250246
- C3: 0.0815611
- C3/C2: **3.259**

Native-slope RMS:

- C2: 0.00023936
- C3: 0.00014857
- C3/C2: **0.621**

Median absolute native slope C3/C2:

**0.576**

So C3 is larger in level excursion but moves more slowly per native bar.

## 3. Instantaneous slope relation

Slope zero-lag correlation:

**approximately 0** (`5.55e-16` overall).

Best retrospective slope-lag absolute correlation over -2048..+2048:

- correlation: **0.0986**
- lag: **-92 bars**

This is weak and is not interpreted causally.

Level zero-lag correlation:

**0.2694**

Best retrospective level-lag correlation:

- correlation: **0.3916**
- lag: **-595 bars**

Again, this is descriptive only.

## 4. Four slope-sign relations

Among nonzero-slope rows:

- `++`: 27.98%
- `+-`: 25.03%
- `-+`: 24.20%
- `--`: 22.79%

No one sign relation dominates the retrospective atlas.

Median relation-state run lengths:

- `++`: 184 bars
- `+-`: 156 bars
- `-+`: 129 bars
- `--`: 142 bars

These long runs are morphology properties of the interpolated graphical residuals, not yet causal state durations.

## 5. Year instability of unconditional sign mix

The four sign-relation fractions vary materially by year.

Examples:

2015:
- ++ 40.69%
- +- 16.66%
- -+ 26.64%
- -- 16.01%

2020:
- ++ 20.21%
- +- 29.91%
- -+ 20.43%
- -- 29.45%

Level correlation also changes sign across years:

- 2015: +0.367
- 2016: +0.063
- 2017: -0.159
- 2018: -0.111
- 2019: +0.235
- 2020: +0.034

Therefore R1 does not support treating any unconditional sign quadrant or raw level correlation as a stable state-machine rule.

## 6. Turn lead/lag morphology

For each C3 turn, the nearest C2 turn has:

- median absolute lag: 0
- q75 absolute lag: 0
- mean absolute lag: 10.59 bars

For each C2 turn, the nearest C3 turn has:

- median absolute lag: 158 bars
- q25/q75: 34 / 370 bars

This is consistent with many C2 turns occurring inside one slower C3 segment.

It is not a causal lead/lag claim.

## 7. Scientific interpretation

The bandpass representation materially differs from comparing two low-pass skeleton directions:

- instantaneous C2/C3 slopes are not highly correlated;
- C3 is slower and larger;
- C3 turns are mostly a subset of C2 turns;
- C2 cycles multiple times inside a C3 structure;
- unconditional sign-state occupancy is time-varying.

This supports continuing to a causal-observability gate, but does not identify a routing state machine.

## Evidence identity

Implementation SHA256:

`14f746ae8991e09f8e634d13ad24ab7b4b1ecccc7e99c5ec9ab39542a24c9318`

Execution result SHA256:

`7ef1292fbfeedabc73dead6c9b55ba19f81aa57c644c00eac9cd75ab3f2f9eeb`

## Boundary

R1 accepts no:

- threshold;
- quadrant;
- lag;
- phase;
- router cell;
- T0/C1 execution preference.

Next stage: R2 causal observability.
