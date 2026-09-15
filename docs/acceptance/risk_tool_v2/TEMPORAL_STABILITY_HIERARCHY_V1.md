# Risk Tool 2.0 Temporal Stability Hierarchy v1

## Purpose

This document turns temporal stability into the optimization objective and stopping rule for Risk Tool 2.0. The tool is not considered complete because a pooled metric is positive. It is complete only when the frozen active acceptance profile passes from coarse to fine time scales.

## Optimization order

The single allowed optimization order is:

1. Global support / ordering / calibration.
2. Annual support / ordering / calibration.
3. Quarterly support / ordering / calibration.
4. Monthly support / ordering / calibration.
5. Weekly support / ordering / calibration.
6. COMPLETE.

The first unresolved gate is the only current optimization target. Lower-frequency detail may be reported diagnostically, but it must not become the optimization target while an earlier gate is unresolved.

Examples:

- `annual.ordering` fails -> work only on annual ordering stability; quarterly/monthly/weekly are blocked as optimization targets.
- annual ordering passes but `annual.calibration` fails -> calibration is the primary contradiction; do not move to quarterly optimization.
- annual passes and `quarterly.ordering` fails -> quarterly ordering becomes the target.
- annual + quarterly + monthly pass and weekly fails -> weekly stability is the final optimization target.

## Frozen balanced thresholds

The active profile is `temporal_stability_profile_hierarchical_v1.json`.

| Level | Coverage | Ordering positive fraction | Calibration joint-positive fraction | Ordering max negative streak | Calibration max negative streak |
|---|---:|---:|---:|---:|---:|
| Annual | 90% | 80% | 70% | 1 year | 1 year |
| Quarterly | 85% | 70% | 60% | 2 quarters | 2 quarters |
| Monthly | 75% | 60% | 55% | 3 months | 4 months |
| Weekly | 60% | 55% | 50% | 6 weeks | 8 weeks |

Every level also requires median ordering gain > 0, sample-weighted mean ordering gain > 0, median calibrated Brier gain > 0, and median calibrated LogLoss gain > 0. Support minima are defined in the machine-readable profile.

## Support is not model failure

If the first unresolved gate is support, the result is `INSUFFICIENT_SUPPORT`. The optimizer must not change the model merely to make a sparsely sampled bucket pass. Support problems and model-instability problems are separate.

## Completion rule

`COMPLETE` requires global support + ordering + calibration and all annual, quarterly, monthly, and weekly support + ordering + calibration gates to pass under the same frozen profile.

A lower level cannot compensate for failure at a higher level. Strong monthly or weekly performance cannot rescue annual instability.

## Change control

Thresholds are adjustable only by creating a new profile id before reading the next fine-grained evaluation. A failed result keeps the profile under which it was produced. Post-result profile switching and rescue retuning are forbidden.

The current active profile is selected by `ACTIVE_TEMPORAL_STABILITY_PROFILE.json` and is frozen before the first real 2015-2025 year/quarter/month/week evaluation.

## Scope boundary

This acceptance mechanism does not compute PnL, search strategy thresholds, refit the model, recalibrate after result reveal, or grant production authority. It measures whether the frozen representation behaves consistently across time scales.
