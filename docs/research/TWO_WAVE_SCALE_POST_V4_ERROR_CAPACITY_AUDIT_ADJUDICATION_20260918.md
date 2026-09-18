# Post-v4 error/capacity audit adjudication — 2026-09-18

Issue #399 diagnoses the already-frozen v4 development OOF only; it does not construct a v5 candidate.

The audit rules out confirmation lag as the main explanation. Of 13 true AMBIGUOUS cases, 6 are never caught by the explicit ambiguity detector at any of 0/5/10/15/25 minutes, 6 are caught at exactly one lag, and only 1 is caught at two lags. Across all true-AMBIGUOUS detection events, seven come from the delta-BIC interval and only one from turn-edge; the two components never fire together. All 13 reference reasons are MIXED_SCALE_COMPETITION.

Validity shows an even sharper split: 14/19 DATA_INVALID cases are never detected at any lag, while 5/19 are detected at all five lags. The selected rule identity still changes across five of six folds. All 19 reference reasons remain the broad DISCONTINUITY_OR_OUTLIER category, so the frozen annotation taxonomy does not explain the hidden subtype boundary.

SUPPORTED/DEVELOPING morphology now has a substantial stable core: 88/136 cases are correct at all five lags (49/75 SUPPORTED and 39/61 DEVELOPING). Dominance-v1 receives most NOT_DOMINANT cases (18–22/24 depending lag), so upstream gating is no longer the only source of dominance error.

The next gate is therefore not calibration v5. A new label-blind diagnostic-family revision must first measure explicit multiscale-competition evidence and validity-subtype evidence. It must be frozen and measured without labels before any later calibration family is designed. No full fit, lag promotion, outcomes/PnL, R4/router, signal/trade, or production authority is granted.
