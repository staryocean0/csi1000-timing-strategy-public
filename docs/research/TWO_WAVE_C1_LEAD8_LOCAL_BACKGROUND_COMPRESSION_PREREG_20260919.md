# C1 lead-8 local-background compression — preregistration

Issue #503. Parent #501 / #498 / #493 / #450.

## Purpose

Test whether C1 turn risk is associated with current 8-bar activity being unusually compressed relative to the recent 32-bar local background.

## Frozen sample

Reuse the exact #493 matched event/control pairs.

- events SHA256: `9723fdc08adcab6d325b6bda450acec4caac9c734a05013911926f749dae8d06`
- matches SHA256: `996c3ecfe5559a50066a37b8f5c96ef34ae09ecf6c3d159d873c8ef7931a662b`

No rematching or sample reselection.

## Causal variables at decision bar k

All use only bars <=k.

Current 8-bar quantities:
- abs_ret8 = |log C[k]/C[k-8]|
- range8 = log(max high[k-7:k] / min low[k-7:k])
- rv8 = std of 8 one-bar log returns ending at k
- efficiency8 = abs_ret8 / sum absolute 1-bar returns over the same 8-return window

32-bar background:
- range32 = log(max high[k-31:k] / min low[k-31:k])
- rv32 = std of 32 one-bar log returns ending at k
- efficiency32 = |log C[k]/C[k-32]| / sum absolute 1-bar returns over the same 32-return window

Primary context-normalized variables:

1. abs_ret8_over_range32 = abs_ret8 / range32
2. range8_over_range32 = range8 / range32
3. rv8_over_rv32 = rv8 / rv32
4. efficiency8_minus_efficiency32 = efficiency8 - efficiency32

Numerical floor 1e-12 is allowed only in denominators.

Lower values mean stronger local compression.

## Estimand

For each frozen event and each feature:

event value minus mean value of its frozen matched controls.

Primary inference unit = event.

Bootstrap 5,000 event resamples, seed 20260919.

## Individual support

A variable supports local-background compression iff:

1. pooled paired median <0;
2. bootstrap 95% upper bound <0;
3. paired median <0 in at least 4 of 6 years;
4. paired median <0 for OLD_UP and OLD_DOWN separately.

## Overall verdict

`C1_LEAD8_LOCAL_BACKGROUND_COMPRESSION_SUPPORTED` iff at least 3 of 4 variables support and >=95% of frozen matched events are computable.

Otherwise:

`C1_LEAD8_LOCAL_BACKGROUND_COMPRESSION_NOT_SUPPORTED`.

## Boundary

No PnL or routing outcome.

A positive result would justify a later causal ranking score based on local relative compression.