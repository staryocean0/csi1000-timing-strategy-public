# C1 lead-8 dynamic contraction specificity — preregistration

Issue #501. Parent #498 / #493 / #485 / #483 / #450.

## Purpose

Static absolute compression ranking failed. Test whether the relevant precursor is dynamic contraction over the most recent 8 bars relative to the immediately preceding 8 bars.

## Frozen matched sample

Reuse the exact #493 matched event/control pairs.

Frozen hashes:
- events ledger: `9723fdc08adcab6d325b6bda450acec4caac9c734a05013911926f749dae8d06`
- matches ledger: `996c3ecfe5559a50066a37b8f5c96ef34ae09ecf6c3d159d873c8ef7931a662b`

No rematching or sample reselection is allowed.

## Windows

For each decision clock k:

Current 8-return window:
- close returns from k-8 to k
- high/low range on bars k-7..k

Previous 8-return window:
- close returns from k-16 to k-8
- high/low range on bars k-15..k-8

All inputs are available at k.

## Primary dynamic features

- delta_abs_ret8 = |log C[k]/C[k-8]| - |log C[k-8]/C[k-16]|
- delta_range8 = current 8-bar log high/low range - previous 8-bar range
- delta_rv8 = std(current 8 one-bar log returns) - std(previous 8 one-bar log returns)
- delta_efficiency8 = current path efficiency - previous path efficiency

Negative means recent contraction.

## Estimand

For each frozen event and each feature:

event dynamic feature minus mean dynamic feature of its frozen matched controls.

Primary inference unit = event.

Bootstrap 5,000 event resamples, seed 20260919.

## Individual support

A feature supports dynamic contraction iff:

1. pooled paired median <0;
2. bootstrap 95% upper bound <0;
3. paired median <0 in at least 4 of 6 years;
4. paired median <0 for OLD_UP and OLD_DOWN separately.

## Overall verdict

`C1_LEAD8_DYNAMIC_CONTRACTION_SUPPORTED` iff:

- at least 3 of 4 primary features individually support dynamic contraction;
- at least 95% of the #493 matched events remain computable.

Otherwise:

`C1_LEAD8_DYNAMIC_CONTRACTION_NOT_SUPPORTED`.

## Boundary

No T0/C1 PnL or route outcome.

A positive result would justify a later causal turn-risk score based on contraction, not absolute compression.