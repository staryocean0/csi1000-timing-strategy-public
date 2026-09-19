# Two-Wave C2/C3 bandpass → T0/C1 execution routing roadmap

Issue #450.

## Goal

Do not design a state machine first.

First determine whether explicit graphical bandpass C2/C3 contains stable state structure that can later route between two execution rhythms:

- E0 = T0
- E1 = T1/C1

## R0 — explicit representation freeze

Deliverables:

- deterministic retrospective S1/S2/S3 polylines;
- explicit C2=S1-S2 and C3=S2-S3 on common occurrence support;
- reconstruction identities;
- support/edge accounting;
- exact source/module/artifact SHA;
- tests.

Hard stop:

- no T0/C1 outcome fields;
- no state threshold search;
- no routing.

Pass requirement:

- deterministic replay;
- monotonic node coordinates;
- no extrapolation outside common support;
- reconstruction numerical tolerance <=1e-12;
- joint C2/C3 support >=90%.

## R1 — morphology atlas

Explore only intrinsic C2/C3 relations:

- sign of native residual slope;
- normalized slope/pace;
- zero-crossing run lengths;
- local extrema spacing;
- residual amplitude;
- phase between turns;
- same/opposite sign occupancy;
- lead/lag of turns;
- C2/C3 amplitude ratio and pace ratio;
- persistence of relationship states.

No execution outcomes visible during this pass.

Output is descriptive evidence, not a rule.

## R2 — causal observability

For every candidate relation variable from R1:

- specify knowledge clock;
- prefix replay;
- evidence age;
- delay from retrospective occurrence to causal availability;
- unresolved fraction;
- stale-state fraction.

Reject variables that only work retrospectively.

## R3 — fair execution contract

Freeze E0 and E1 independently:

- own trigger;
- own entry;
- own exit/lifecycle;
- cost convention;
- overlap handling;
- simultaneous-opportunity handling;
- comparison unit.

A fixed T0 holding interval with C1 used only as opposite direction is not sufficient.

## R4 — relationship-to-execution discovery

Join only R2-qualified C2/C3 state variables to R3 frozen E0/E1 matched outcomes.

Primary quantities:

- delta value E1-E0;
- downside regret;
- upper/lower tail;
- win frequency secondary;
- year/parent-state cluster uncertainty.

Do not fit a production router.

## R5 — candidate state machine

Only after R4 finds stable structure:

- preregister exact states;
- exact thresholds or partitions;
- exact fallback/abstention;
- walk-forward protocol;
- no cell merging after outcomes.

## R6 — independent validation

Development evidence cannot authorize production.

Require a separately frozen independent period/source.

## Stop conditions

Stop and redesign if:

- B3 representation support is insufficient;
- causal observability fails;
- E0/E1 cannot be compared fairly;
- R4 structure is unstable across time/clusters;
- state-machine complexity grows without incremental stability.

## Historical handling

All prior C2 phase/deadband/persistence/router results remain immutable historical evidence.

They may motivate diagnostics but cannot select new thresholds after outcome exposure.
