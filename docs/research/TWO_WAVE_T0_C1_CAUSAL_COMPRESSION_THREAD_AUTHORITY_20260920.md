# Two-Wave T0 / C1 causal compression thread — authority narrative

Date: 2026-09-20.

Status:

`C1_COMPRESSION_CAUSAL_FRAGILITY_SUPPORTED__STATIC_RELATION_INTERACTION_NOT_SUPPORTED`

This document is the current authority narrative for the T0/C1 causal-compression side thread. It does not replace the C2/C3 routing-thread authority.

## Accepted causal evidence

1. Authoritative #507 v2:
   `C1_COMPRESSION_RISK_RANKING_SUPPORTED`.
   Direction-agnostic 8-bar compression ranks the probability of a retrospective C1 turn in the next 8 bars.

2. #537:
   compression predicts T0 fast-loss hazard more clearly than mean-return degradation.

3. #540:
   uniform defer-8 on high compression is not supported.

4. #607 / #609:
   symmetric directional alerting from signed ret8 is not supported.
## Interaction evidence

Historical #571 B1-vs-B5 causal C1-relation interaction:

`C1_COMPRESSION_T0_INTERACTION_NOT_SUPPORTED`.

Issue #615 repeated the interaction question under a separately preregistered, higher-support grouping:

- LOW = B1+B2
- MID = B3
- HIGH = B4+B5

and required four primary cells to meet minimum support before inference.

All support gates passed, but the three bootstrap CI gates failed.

Issue #615 verdict:

`T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED`.

Therefore current causal C1 relation × compression risk does not authorize a router, veto, or override.
## What remains true

T0 keeps responsibility for trade direction.

C1 is still first-class context, but current causal C1 leg direction cannot replace the retrospective C1 oracle and cannot supervise T0 direction directly.

Compression remains a causal fragility / turn-risk variable:

- useful for ranking C1 near-term turn risk;
- useful for identifying elevated T0 fast-loss hazard;
- not validated as a stable mean-return filter;
- not validated as a static interaction with causal C1 ALIGNED/OPPOSED relation.

Negative interaction results must not be rescued by moving B1..B5 boundaries or post-hoc cell merging.

## Controlled execution acceptance

Issue #615 has completed the standard governed execution path and is ready for issue closure.

Authoritative public workflow run: `35477767158` / identity `35477767158-1`, public source SHA `55ae1f76c22db03c2e212913bcd07bdf30b5f5f8`.

The private receipt, Release archive and independent verifier were read back and hash-verified. Exact result SHA256 remains `6a7518075565cb7c027b900764e4846fa937e4ccf83a0739817420d860a7b73a`; joined ledger SHA256 remains `3d16639e49994283a9f0027a94e5dcf9c9a1d26a66280efe3adb86da9873a45a`.

See `TWO_WAVE_T0_CAUSAL_C1_COMPRESSION_INTERACTION_EXECUTION_ACCEPTANCE_20260920.*`.

## Pending #612

Issue #612 remains preregistered and unexecuted at this authority update.

It has narrow incremental value only because it formalizes a stricter one-dimensional economic hierarchy:

- B5 veto test;
- B5-vs-B1 risk-downgrade test;
- B5-specific fast-loss and mean-net confidence intervals.

Most of its evidence overlaps #537. It should be treated as a formal adjudication/closure study, not as a new model-development direction.

## Boundary for the next independent hypothesis

A successor must not re-run:

- static causal C1 relation × compression;
- symmetric ret8 direction guessing;
- uniform defer-8;
- high-compression weak-thrust rule;
- current causal-state fragility map.

A genuinely new hypothesis should target a different causal object, such as within-trade path timing or hazard transition dynamics, and must be preregistered before outcome inspection.

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.
