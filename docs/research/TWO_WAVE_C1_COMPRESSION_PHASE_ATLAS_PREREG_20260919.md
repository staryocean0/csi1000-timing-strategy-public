# Conditional C1 turn-risk atlas: local compression × causal C1 phase — preregistration

Issue #509. Parent #505 / #503 / #493 / #450.

## Objective

Test whether the already-frozen local-background compression score has conditional C1-turn-risk information inside the then-known causal C1 phase.

Do not change the #505 score to rescue its failed global ranking.

## Decision universe and target

Reuse #505 exactly:

- decision bars = T0 period-21 signal bars;
- test years = 2018, 2019, 2020;
- target turn_next8 = retrospective dense C1=S0-S1 slope turn occurs in (k,k+8].

Target is evaluation-only.

## Frozen compression score

Reuse the three #503-supported features:

1. abs_ret8_over_range32
2. range8_over_range32
3. efficiency8_minus_efficiency32

For each test year, use prior-year T0 signal bars to construct the empirical feature percentiles exactly as #505.

Lower percentile means stronger compression.

compression_score = equal-weight mean of (1 - percentile) across the three features.

No phase-specific recalibration. No fitted weights. No threshold search.

## Causal phase

At each T0 signal bar use `causal_state` from the stage-1 continuity state.

Frozen phase:

- EARLY if age_ratio < 1/3
- MIDDLE if 1/3 <= age_ratio < 2/3
- LATE if age_ratio >= 2/3

UNRESOLVED is reported but not eligible for conditional acceptance.

## Per-phase metrics

For EARLY / MIDDLE / LATE separately, pooled and by test year:

- N signal bars
- turn-next8 count / baseline rate
- AUROC
- average precision
- compression-score quintile turn rates
- quintile-rate Spearman
- top20 score turn rate and lift over the same phase baseline
- bottom20 score turn rate

Top20 pooled lift receives a 20-trading-day T0-signal block bootstrap, 5,000 resamples, seed 20260919.

## Phase-level conditional support gate

A phase is marked `COMPRESSION_CONDITIONALLY_USEFUL` only if all are true:

1. pooled phase N >=150 and at least 30 signal bars in each test year;
2. pooled AUROC >0.55;
3. AUROC >0.52 in at least 2 of 3 test years;
4. pooled top20 lift >=1.30;
5. top20-lift bootstrap 95% lower bound >1.0;
6. pooled quintile-rate Spearman >0.

Otherwise the phase is `COMPRESSION_CONDITIONALLY_NOT_SUPPORTED`.

## Overall interpretation

If no phase passes:
`C1_COMPRESSION_PHASE_CONDITIONING_NOT_SUPPORTED`.

If one or more phases pass:
`C1_COMPRESSION_PHASE_CONDITIONING_CLUE_FOUND`.

Because all three phases are inspected on consumed development data, a passing phase is still discovery evidence and requires a separately frozen validation study before use.

## Boundary

No PnL or route outcome.

No phase-dependent trading rule or threshold is authorized.