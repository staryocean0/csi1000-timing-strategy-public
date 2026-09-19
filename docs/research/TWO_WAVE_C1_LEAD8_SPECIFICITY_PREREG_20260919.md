# C1 lead-8 precursor specificity — matched-control preregistration

Issue #485. Parent #483 / #450.

## Purpose

The discovery atlas found a candidate pattern:

at k=t-8 before a final retrospective C1 slope turn, recent raw returns tend to align more strongly with the OLD C1 direction, equivalently oppose the future turn direction.

Before treating this as a precursor, test it against matched non-turn controls.

## Oracle and event clock

Use the same retrospective dense C1=S0-S1 native-slope turn oracle as #483.

For each turn event t:

- decision clock k=t-8;
- current retrospective C1 sign at k is the OLD direction;
- event label = a C1 slope turn occurs exactly 8 bars later.

## Control eligibility

A control decision bar kc is eligible for an event iff:

1. same calendar year as the event;
2. same retrospective C1 slope sign at kc as the event's OLD sign at k;
3. same age-since-last-C1-turn decile;
4. no retrospective C1 turn occurs in bars (kc, kc+8];
5. raw-feature windows are fully available;
6. control is at least 16 bars away from the event decision clock to avoid direct overlap.

For each event, sample up to 5 controls without replacement from eligible bars using seed 20260919.

Controls may be reused across different events only if the candidate pool is insufficient for unique global matching; reuse count must be reported.

## Primary variables at the decision clock

All are observable from raw bars at k.

Signed by the OLD retrospective C1 direction for analysis:

- thrust_8 = old_sign * ret_8
- thrust_16 = old_sign * ret_16
- thrust_32 = old_sign * ret_32

Unsigned:

- abs_ret_8
- range_8
- rv_8
- efficiency_8

Negative/mechanical controls:

- age_since_last_base_confirmation
- causal_c1_evidence_age

The OLD sign is used only for retrospective mechanism alignment, not proposed as an operational live input.

## Estimands

For each variable:

- event median
- matched-control median
- paired event minus mean-of-controls difference per event

Primary inference unit = event.

Bootstrap 5,000 event resamples, seed 20260919.

Report 95% CI for the median paired difference.

## Specificity criterion for terminal thrust

TERMINAL_THRUST_SPECIFICITY_SUPPORTED iff all are true for thrust_8:

1. event median > matched-control median;
2. bootstrap 95% lower bound for paired median difference >0;
3. point difference is positive in at least 4 of 6 years;
4. point difference is positive separately for OLD_UP and OLD_DOWN events.

thrust_16 and thrust_32 are supporting diagnostics.

## Direction-prediction diagnostic

Among turn events only, report:

P(sign(ret_8) == old_sign)

and equivalently:

P(-sign(ret_8) == future_turn_direction).

This is diagnostic only; no thresholded predictor is frozen here.

## Boundary

No T0/C1 PnL or routing outcome.

A positive specificity result only justifies a later causal predictor study.
