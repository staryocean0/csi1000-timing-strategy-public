# Calibration v3 development LOYO adjudication — 2026-09-18

Coverage-aware calibration v3 repairs the v2 abstention collapse without adding raw features. Across the frozen 0/5/10/15/25 minute confirmation family, morphology emits only 0–2 ambiguous component predictions per 192 panels; at lag 0, CURRENT_SCALE_SUPPORTED to TURNING_OR_COMPLETED is 64/75 and CURRENT_SCALE_DEVELOPING to DEVELOPING_ONE_LEG is 45/61.

This is not a readiness pass. The explicit AMBIGUOUS_MULTI_SCALE reference class is now almost entirely missed: 1/13 at lag 0 and 0/13 at every positive lag. The validity guard is also unchanged at only 7/19 DATA_INVALID_EDGE recall with 8/173 false invalids. Dominance recovers useful development discrimination (16–18/24 NOT_DOMINANT recall depending on lag) but does not override the ambiguity/validity blockers.

No confirmation lag is selected or promoted from this consumed development population. Lag 0 has the highest descriptive exact-state count (127/192), but that is not selection authority. No full-192 fit, label relaxation, case exceptions, PnL tuning, R4, routing, signal/trade or production promotion is authorized.

Next allowed step: preregister a v4 calibration family that keeps the repaired coverage objective but makes the reference AMBIGUOUS class an explicit training target and broadens the validity rule family using only already-measured v2 evidence. Fresh independent OOS remains required for readiness.
