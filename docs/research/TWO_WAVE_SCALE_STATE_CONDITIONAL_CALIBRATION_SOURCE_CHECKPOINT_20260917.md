# #376 state/morphology-conditional calibration — source checkpoint

This checkpoint is **before** any real 192-case OOF calibration fit.

The label-blind validity measurement completed as public run `35221426711-1` from merged source `1458a282832d8a077d3db3cb85eeeaf0f314be49`. The private receipt is `passed / archive_uploaded_and_verified`; frozen validity diagnostics SHA256 is `5e7199a3ae42816751a353d7ca6d4fdbd11281e24666fa6de43e499fc42931e8`.

The calibration engine is now implemented as pure source in `executor/wave_scale_state_conditional_calibration_v1.py`. It performs deterministic leave-one-calendar-year-out fitting for 2015–2020 and preserves three separate objects: validity, morphology, and morphology-conditional current-scale dominance.

No single composite dominance score is introduced. Calendar year is a fold key only. Amplitude is not an accept/reject feature. The formal validity run saw no reference labels, future suffix, outcomes, PnL, R1/R2/R3 classes, or state thresholds.

The binary validity/dominance rule family contains a null rule, one-feature rules, and at most two-feature AND/OR rules. Numeric thresholds are training-fold empirical midpoints only. Missing evidence remains UNKNOWN; it is never imputed.
Validity and dominance training impose the pre-fit 5% false-rejection cap. Within that feasible set they maximize detection of the relevant rejection class, then minimize false rejection, UNKNOWN/abstention, and rule complexity. If no useful rule survives, the scientific gate fails rather than relaxing the cap.

Morphology is fit independently from five-phase shape counts and at most one turn-location-dispersion threshold. The pre-fit objective maximizes correct SUPPORTED/DEVELOPING decisions first, then minimizes wrong decisions and ambiguity, preventing an all-abstain rule from winning.

The real OOF input identities are already frozen independently: dominance diagnostics `aed0b65305f06d36dfd679df4ee75feb48b246a40e3a5e39831cefedf2ee3baa`, final reference labels `6fb36ee74413c9b7e95824a94a89bec74a493513668a36b3373c24518fc834be`, and v3 full inventory/calendar mapping `32f6279610def838474fb0bc4596c33dfb41f88e4fb78e4a20d6b39942446206`.

At this checkpoint: real OOF fit = **not run**; numeric validity/dominance thresholds = **not selected**; full-192 candidate v1 fit = **not run**; future suffix remains unrevealed; no R4, scale router, 1m trading strategy, signal/trade/PnL or production authority is granted.

The next allowed action is: merge/review this source checkpoint, then run the frozen LOYO algorithm once on the four frozen objects above and adjudicate OOF stability before any full-192 candidate calibration.