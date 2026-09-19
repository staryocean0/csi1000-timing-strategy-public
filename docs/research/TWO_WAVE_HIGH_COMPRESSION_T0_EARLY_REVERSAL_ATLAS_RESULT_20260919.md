# High-compression T0 early-reversal precursor atlas — result

Issue #543. Parent #540/#537/#507/#450.

## Status

`HIGH_COMPRESSION_T0_EARLY_REVERSAL_ATLAS_COMPLETE`

Frozen universe: #507 B4+B5, N=356.

- EARLY_REVERSAL: 45 (12.64%)
- SURVIVES_8: 311

## Accepted continuous clues

1. `risk_abs_ret_8`
   - AUC 0.611
   - early median 0.8554 vs survive 0.7889
   - median difference CI excludes 0
   - same sign all 3 years.

2. `ret_aligned_8`
   - raw-orientation AUC 0.391
   - early group has weaker T0-side 8-bar thrust
   - median difference -0.000396
   - CI [-0.000984,-0.000032]
   - same sign all 3 years.

3. `compression_score`
   - AUC 0.600
   - early median 0.7468 vs survive 0.7018
   - difference CI [0.0114,0.0961]
   - same sign all 3 years.

4. `range_8`
   - raw-orientation AUC 0.410
   - early group is narrower
   - difference CI [-0.000930,-0.000006]
   - same pooled direction in 2/3 years.

## Categorical observations

- B4 early-reversal rate: 7.82%
- B5 early-reversal rate: 17.51%

Other causal hierarchy states are much weaker:
- causal C1 leg aligned 13.6% vs opposed 12.1%
- C1 phase EARLY 10.3%, MIDDLE 12.0%, LATE 14.4%.

## Interpretation

The dominant causal pattern is not a richer C1 state label.

It is the combination of:

> high direction-agnostic compression + weak recent T0-side directional thrust.

This motivates a simple label-free stall-risk ranking rather than another C1-state classifier.

## Evidence

- module SHA256 `cf60d661d3af95f56e10f284038fdecac975a5be465ebbe23a190810eedbac59`
- feature ledger SHA256 `ecb871ae728e24198a05309e24699b6baad2e5b18440e55a0bce03a2ad32f327`
- exact result SHA256 `e59dd1add978f319450a1a49ab30009b53bcb906fcd29d47a36b416b691b3577`

No classifier, veto, trade or production authority.