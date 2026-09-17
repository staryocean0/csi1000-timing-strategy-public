# State/morphology conditional LOYO adjudication — 2026-09-17

Issue #376 executed the frozen six-fold leave-one-calendar-year-out engine only after the calibration source merged as `420bf593b2246072ef1ccfc883ca9bb8439cc4d8`. No full-192 fit was performed.

The OOF evidence blocks candidate-v1 full fitting. The validity guard recalled only 7/19 `DATA_INVALID_EDGE` references while falsely rejecting 10/173 non-invalid references, and the six folds selected five distinct validity rule identities. Morphology was stable in rule identity but classified only 34/61 `CURRENT_SCALE_DEVELOPING` cases as `DEVELOPING_ONE_LEG`; 27/61 were called turning. The operational rule family emitted zero `AMBIGUOUS_MULTI_SCALE` predictions, so ambiguity recall was 0/13.

Conditional dominance is comparatively stronger: false current-scale rejection was 4/136 and `CURRENT_SCALE_NOT_DOMINANT` recall was 18/24, with two turning-rule identities and three developing-rule identities. This is retained as control evidence only; it does not override the validity/morphology failures.

Per the preregistered stop rule, the project does **not** fit all 192 cases, relax labels, add case exceptions, or optimize PnL. The next allowed step is a separately preregistered v2 diagnostic-family revision addressing discontinuity validity, developing-vs-turning morphology, and an explicit ambiguity mechanism.

Public aggregate: `docs/research/TWO_WAVE_SCALE_STATE_CONDITIONAL_LOYO_AGGREGATE_20260917.json` (SHA256 `72fef2796ea0a3bd9203310b5c5ee6c5f60c850cff2d51fed08f385e699f3403`). Detailed panel-level OOF predictions remain private evidence only.
