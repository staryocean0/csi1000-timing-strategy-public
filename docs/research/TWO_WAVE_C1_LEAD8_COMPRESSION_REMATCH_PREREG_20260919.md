# C1 lead-8 compression specificity under evidence-age rematching — preregistration

Issue #493. Parent #485 / #483 / #450.

## Purpose

Test whether the apparent pre-turn compression at k=t-8 survives stricter matching on information-age variables.

## Oracle

Same retrospective dense C1=S0-S1 native-slope turn oracle as #483/#485.

For each event turn t, decision clock is k=t-8.

## Controls

Each control must satisfy:

1. same calendar year;
2. same retrospective OLD C1 sign;
3. same retrospective age-since-last-C1-turn decile;
4. same age-since-last-base-confirmation quintile;
5. same causal-C1-evidence-age quintile;
6. no retrospective C1 turn in (kc,kc+8];
7. |kc-k_event| >=16 bars;
8. all raw feature windows available.

Age deciles/quintiles are computed inside calendar-year × OLD-sign candidate populations.

Use up to 5 controls per event, seed 20260919, with globally unused controls preferred before reuse.

## Primary causal variables at k

- abs_ret_8
- range_8
- rv_8
- efficiency_8

These are unsigned and require no future direction label at live use.

## Estimand

For each event and variable:

event value minus mean matched-control value.

Primary inference unit = event.

Bootstrap 5,000 event resamples, seed 20260919.

## Compression support criterion

A variable individually supports compression iff:

1. pooled paired median <0;
2. bootstrap 95% upper bound <0;
3. paired median <0 in at least 4 of 6 years;
4. paired median <0 for OLD_UP and OLD_DOWN separately.

Overall verdict:

C1_LEAD8_COMPRESSION_SPECIFICITY_SUPPORTED iff at least 3 of 4 primary variables individually support compression, matched-event coverage >=80%, and median controls per matched event >=4.

Otherwise:

C1_LEAD8_COMPRESSION_SPECIFICITY_NOT_SUPPORTED.

## Balance diagnostics

Report residual event-control difference after rematching for:

- age_since_last_base_confirmation
- causal_c1_evidence_age

These are balance checks, not signal variables.

## Boundary

No T0/C1 PnL or routing outcome.

A positive result only authorizes a later causal turn-risk predictor study.