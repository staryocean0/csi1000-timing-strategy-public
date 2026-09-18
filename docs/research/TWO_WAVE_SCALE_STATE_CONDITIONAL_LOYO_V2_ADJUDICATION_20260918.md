# State-conditional v2 development LOYO adjudication — 2026-09-18

Issue #381 executed the six-fold 2015–2020 leave-one-calendar-year-out evaluation only after the v2 raw diagnostic object was frozen and the calibration family itself was source-frozen as commit `a735a9a78a37dd2bc5bdeeba2682cf4fece4ecb2`. This is iterative development evidence, not fresh OOS.

The result is **not ready for a full-192 fit**. Validity false-invalid error improved from v1 to `8/173 = 4.62%`, but `DATA_INVALID_EDGE` recall remained only `7/19 = 36.84%`, while 130/192 cases were left `UNCERTAIN_VALIDITY`.

Morphology failed in the opposite direction from v1: the explicit two-boundary family over-abstained. Only `5/75` supported references were called `TURNING_OR_COMPLETED`, only `5/61` developing references were called `DEVELOPING_ONE_LEG`, and `177/192` morphology-component predictions were `MORPHOLOGY_AMBIGUOUS`.

The final output marked `172/192` cases ambiguous. Therefore the apparent `13/13` recall on the true ambiguous reference class is not a success criterion; it is a consequence of excessive abstention.

Because upstream validity/morphology left almost no branch-qualified training support, every turning/developing dominance fit selected the frozen v1 family’s `NULL` rule. Operational `CURRENT_SCALE_NOT_DOMINANT` recall was therefore `0/24`; this does **not** overturn the earlier v1 dominance evidence, because the v2 upstream gate prevented a meaningful conditional dominance test.

The private panel-level OOF SHA256 is `99b6e5ee6545d5982d3acf5eaa1a8275d88c1ca5077bd82c9e080d2aea0402a9`. The public aggregate SHA256 is `7b14d15d016c63311c2f9b27cf41f3882705369d1d69af46c270f0abc349afc9`. No panel→label or panel→feature mapping is published.

Per the stop rule, the project does not fit all 192 cases, relax labels, add case exceptions, optimize PnL, activate R4/router, or claim production authority. The next permitted research action is a separately preregistered v3 calibration-objective/validity-family revision; any final readiness claim still requires a newly sampled independent blind reference population after development stabilizes.
