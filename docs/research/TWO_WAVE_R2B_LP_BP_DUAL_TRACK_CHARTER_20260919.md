# R2b dual-track causal observation charter

Date: 2026-09-19.

Parent: #450. Representation fork: #463. R2b scope: #461.

## Status

`LP_BP_PARALLEL_CAUSAL_QUALIFICATION_REQUIRED`

Pass A did not identify an early winner.

Therefore both representations remain active:

- LP track: LP2=S1, LP3=S2
- BP track: BP2=S1-S2, BP3=S2-S3

## Why both remain

Lowpass has substantially better exact observability and slightly longer relation runs, while preserving a clear ~4x adjacent-scale hierarchy.

Bandpass has much cleaner layer separation and slightly lower year-to-year relation-state drift.

Neither representation Pareto-dominated the other under the frozen Pass-A rule.

## Fair-comparison rule

The two tracks must be treated symmetrically.

For every causal observation family admitted later:

1. the same knowledge clock is used;
2. the same raw information set is used;
3. the same delay grid is used;
4. the same fidelity metrics are used;
5. the same temporal-stability rules are used;
6. no T0/C1 execution outcome is visible during family selection;
7. any family-specific parameter budget must be equal in complexity.

A method may not be introduced for only one representation merely because it looks promising after seeing results.

## R2b execution sequence

### R2b-0 — observation-family registration

Freeze a small causal observation family or families before measuring LP/BP fidelity.

No execution outcome.

### R2b-1 — paired causal fidelity measurement

For every registered family and delay:

- LP2/LP3 fidelity
- BP2/BP3 fidelity
- component sign fidelity
- joint relation fidelity
- turn timing
- excess-turn/oversegmentation
- latency
- yearly stability
- prefix replay

### R2b-2 — representation comparison

A representation may be dropped only if it is rejected by a preregistered comparative rule.

If both remain viable, both continue to the same frozen E0/E1 execution contract.

### R2b-3 — only after causal qualification

Only qualified LP/BP states may be joined to T0/C1 execution outcomes.

No retrospective final state may be backfilled.

## Current evidence snapshot

Pass A:

Lowpass:
- joint support 99.29%
- median exact joint delay 367 bars
- slower/faster turn-spacing ratio 4.21
- pooled relation-run median 158.5
- yearly relation-fraction drift 0.04371

Bandpass:
- joint support 98.28%
- median exact joint delay 1561 bars
- slower/faster turn-spacing ratio 3.62
- pooled relation-run median 151
- yearly relation-fraction drift 0.03729

Verdict:

`NO_EARLY_WINNER__ADVANCE_BP_AND_LP_IN_PARALLEL`

## Authority

No signal/router/trade/paper/live/production authority.
