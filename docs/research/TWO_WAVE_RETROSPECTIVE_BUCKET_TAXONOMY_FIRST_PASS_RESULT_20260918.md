# Retrospective bucket taxonomy — first-pass result (2026-09-18)

## Verdict

**The three-bucket hypothesis is rejected.**

The project cannot use only:

1. current-scale;
2. low-volatility not-current-scale;
3. high-volatility not-current-scale.

Existing frozen evidence already contains residual mechanisms that cannot be merged by volatility magnitude without losing structural meaning.

## Frozen 192-case audit

The blind reference set contains 192 panels.

Current-scale bucket:
- CURRENT_SCALE_SUPPORTED = 75
- CURRENT_SCALE_DEVELOPING = 61
- B0 CURRENT_SCALE = **136 / 192 = 70.83%**

After removing B0, 56 panels remain:

- REPEATED_SHORTER_STRUCTURE = **24 / 56 = 42.86%**
- MIXED_SCALE_COMPETITION = **13 / 56 = 23.21%**
- DISCONTINUITY_OR_OUTLIER = **19 / 56 = 33.93%**

These are already three different mechanisms inside the residual population. Therefore “residual = low volatility vs high volatility” is not an exhaustive structural taxonomy.

## Why a coarser-scale bucket remains necessary

In the earlier blindspot relocation study, 144 reset-root blind episodes were examined retrospectively. C2 supplied majority overlap for 143/144 and C3 for 142/144.

That result does not prove that high amplitude equals coarse scale. It does prove that a larger parent-scale explanation exists as a distinct structural mechanism and therefore cannot be removed from the candidate taxonomy before a dedicated retrospective adjudication.

## Why a no-resolvable-structure bucket remains provisional

The frozen 192 reference happened to have zero INSUFFICIENT_SUPPORT cases. However, synthetic controls and historical state-completeness work already contain valid near-flat, monotone and unfinished paths that do not form a completed current-scale cycle.

Therefore B4 remains provisional. The next retrospective packet must determine whether:
- B4 occurs materially in real historical intervals and remains separate; or
- B4 can be merged/eliminated without leaving any unresolved interval.

## Working taxonomy after first pass

- B0 CURRENT_SCALE
- B1 FINER_SCALE_DOMINANT
- B2 COARSER_SCALE_DOMINANT
- B3 MIXED_MULTI_SCALE
- B4 NO_RESOLVABLE_STRUCTURE — provisional
- B5 DATA_INVALID_OR_EDGE

**Working count: 6. Final count: not yet frozen.**

The next study is not an identification-rule study. It is a blinded retrospective taxonomy packet whose purpose is to prove the minimum exhaustive bucket count.

## Stop condition before recognizer work

Recognizer design remains blocked until:
- every retrospective audit interval has exactly one final bucket;
- TAXONOMY_UNRESOLVED = 0;
- bucket conflict = 0;
- two blind annotation passes plus adjudication are frozen;
- no bucket definition depends solely on amplitude/volatility;
- B5 remains separate from market-regime buckets.

Only after that freeze does the project design recognition rules and the 8×5m delayed endpoint wrapper.
