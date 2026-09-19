# Conditional C1 turn-risk atlas: local compression × causal C1 phase — result

Issue #509. Parent #505 / #503 / #493 / #450.

## Verdict

`C1_COMPRESSION_PHASE_CONDITIONING_NOT_SUPPORTED`

The failed global local-background compression score from #505 does not become a stable turn-risk ranking after conditioning on the then-known causal C1 phase.

The exact #505 score was reused without any feature, weight, percentile, or threshold change.

## Support

OOF T0 signal bars, 2018–2020:

- EARLY: 197
- MIDDLE: 318
- LATE: 434
- UNRESOLVED: 0

Global #505 replay was exact:

- N = 949
- pooled AUROC = 0.49652561507318593
- test-year counts = 297 / 319 / 333

## EARLY

Pooled:

- N: 197
- turn rate: 12.69%
- AUROC: 0.530
- quintile-rate Spearman: +0.30
- top20 lift: 1.576

But:

- top20-lift bootstrap 95% CI: [0.689, 2.544], crosses 1
- only 1/3 years has AUROC >0.52
- 2020 top20 turn rate is 0

Verdict:

`COMPRESSION_CONDITIONALLY_NOT_SUPPORTED`

## MIDDLE

Pooled:

- N: 318
- turn rate: 24.53%
- AUROC: 0.540
- quintile-rate Spearman: +0.667
- top20 lift: 1.083

All three yearly AUROCs are slightly >0.52, but the ranking is too weak and unstable:

- 2018 AUROC 0.549
- 2019 AUROC 0.523
- 2020 AUROC 0.558
- top20-lift bootstrap 95% CI: [0.733, 1.460]

Verdict:

`COMPRESSION_CONDITIONALLY_NOT_SUPPORTED`

## LATE

Pooled:

- N: 434
- turn rate: 24.19%
- AUROC: 0.455
- quintile-rate Spearman: -0.30
- top20 lift: 1.140

The phase is strongly unstable:

- 2018 AUROC 0.572
- 2019 AUROC 0.437
- 2020 AUROC 0.346

In 2020 the score is almost monotonically reversed across quintiles.

Verdict:

`COMPRESSION_CONDITIONALLY_NOT_SUPPORTED`

## Interpretation

The #493/#503 compression relation is real as a matched-event precursor, but it is not a globally monotonic risk score and is not rescued by EARLY/MIDDLE/LATE phase conditioning.

Therefore:

- do not tune phase-specific compression thresholds;
- do not rescue the score with new phase-specific weights;
- do not promote LATE-phase compression as a C1-turn warning.

The next research direction should move away from raw compression score rescue and inspect lower-level structural timing information that is causally available before the C1 turn.

## Evidence identity

- module SHA256: `dfc7dd07f28cf5349c6bc877fc6e6c647f0426b634ec5705a04d907f34188202`
- scored ledger SHA256: `daa96a2a28798125bb126033f6defe31bc21fc8295cabe3933dfed9d281e0d0d`
- exact result SHA256: `bc9c4c5c02542be2f78c950acf5c854e4de79d2ab2f7a919bc530cec4da7e85a`

## Boundary

No PnL or routing outcome was used.

No signal, router, paper/live, trade or production authority.
