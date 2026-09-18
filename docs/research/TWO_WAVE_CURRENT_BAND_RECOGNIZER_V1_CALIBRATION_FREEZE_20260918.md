# Two-Wave current-band recognizer V1 — calibration freeze

Issue #420. Target oracle: frozen V2.1 primary taxonomy.

## Status

`CALIBRATION_FROZEN_PROTECTED_UNOPENED`

The recognizer family and the five fitted convex weights are frozen before protected evaluation.

### Pre-protected numerical-stability amendment

Commit `f49229a` recorded the first calibration freeze, but two calibration `CURRENT_RANGE` samples landed numerically at `D=+0.20`; deterministic runtime replay evaluated those scores a few floating-point ulps above the frozen threshold. The protected labels were still permission mode `000` and had never been opened.

Before any protected evaluation, calibration was rerun with a solver-only `1e-4` interior stability margin around ±0.20. The model family, coordinates, LOW/FINER gates and runtime thresholds did not change. The resulting weights below supersede the pre-protected weights from `f49229a`. Git history retains that earlier checkpoint.

Target oracle SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

## Frozen split

- calibration rows: 322
- protected evaluation rows: 78
- split manifest SHA256: `0f274d6500a04c059bfb4dc833417bd881c683389f33b42fb2f11f325b007ebd`
- calibration labels SHA256: `50d39c9affc1c6e31be0f8a006b22a309f09be294c8141efbbba4a27c789efd7`

The protected-label file remained permission mode `000` throughout calibration.
## Fixed semantic gates

Before fitting any weight:

- LOW calibration support: 34
- LOW recall: 34/34 = 1.0
- LOW false positives: 0
- FINER calibration support: 2
- FINER recall: 2/2 = 1.0
- FINER false positives: 0

Neither LOW nor FINER contains a fitted parameter.

The direction problem therefore contains 286 calibration rows.

Calibration feature matrix SHA256:

`a33c325ccabc2cc51d330b4176f001f59909a5d95e3176edd5d04a1d5ab0c272`
## Deterministic optimization

Only the five nonnegative direction weights are fitted.

Constraints:

- every weight >= 0;
- the five weights sum to 1;
- formal direction threshold remains ±0.20.

Optimization is lexicographic:

1. maximize exact direction identity;
2. among ties, maximize macro direction recall;
3. among remaining ties, minimize the maximum single weight.

A solver-only stability margin of `1e-4` is imposed around ±0.20 during calibration so a fitted RANGE example is not left on a floating-point boundary.

This margin does **not** change the runtime classifier threshold, which remains exactly ±0.20.

The global direction optimum is 263 / 286.
## Frozen weights

In order `[phase0, phase1, phase2, phase3, raw_minleg4]`:

- phase0: `0.5375062131339785`
- phase1: `0.02424630935968975`
- phase2: `0.2550411892804524`
- phase3: `0.08498791874772484`
- raw_minleg4: `0.0982183694781545`

Maximum single weight: `0.5375062131339785`.

Minimum calibration score distance from either runtime threshold after freezing:

`9.999999999960041e-05`
## Calibration replay

Exact five-state identity:

`0.9285714285714286`

Macro recall:

`0.9484265350877192`

Per-state recall:

- CURRENT_UP: `0.9333333333333333`
- CURRENT_RANGE: `0.8947368421052632`
- CURRENT_DOWN: `0.9140625`
- LOW_AMPLITUDE_VETO: `1.0`
- FINER_SCALE_OUT_OF_BAND: `1.0`

The minimum state recall is `0.8947368421052632`.

All preregistered progression gates pass.
## Frozen local evidence

Calibration receipt SHA256:

`04616d33463efd7760894f1a30e355959fbae122e08244600618ecaaa2b780ca`

Calibration freeze checkpoint SHA256:

`8f237fecc911ea01bdc324a51df61a30b7a843324d68ec117d2ea7dc35de0067`

No 128/256 context, date/year, challenge stratum, future return, PnL, trade outcome or protected label was used.

## Next step

The 78 protected labels may now be opened exactly once.

After protected evaluation is opened:

- these five weights cannot change under V1;
- LOW/FINER gates cannot change;
- direction coordinates cannot change;
- ±0.20 cannot change.

A protected failure would reject V1 rather than trigger retuning.

The delayed `8 × native 5m` wrapper remains blocked until retrospective recognizer acceptance.
