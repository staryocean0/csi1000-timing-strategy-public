# T0 path/hazard atlas across causal C1 compression bands — preregistration

Issue #587. Parent #582 / #507 / #450.

## Objective

Decompose the monotone fast-loss gradient found in #582 into trade-path timing without changing the T0 strategy.

## Frozen universe

Use authoritative #507 v2 walk-forward T0 signal ledger (2018–2020, N=945) and join one-to-one to the frozen period-21 T0 own-lifecycle trades.

Reuse B1..B5 compression bands exactly. No score/band retuning.

## Horizons

Evaluate at h = 4, 8, 16, 21, 24, 32 native bars after T0 entry.

## Per-trade horizon state

For trade with entry open e and actual exit open x:

- exited_by_h = 1 iff duration <= h;
- losing_exit_by_h = 1 iff duration <= h and gross_log_return < 0;
- winning_exit_by_h = 1 iff duration <= h and gross_log_return > 0;
- survival_by_h = 1 - exited_by_h.

Realized-or-MTM value_h:

- if duration <= h: use actual net_log_return_proxy;
- otherwise, if entry+h is inside source data: side * log(open[entry+h]/open[entry]) - 4bp;
- otherwise missing for that horizon.

Survivor_MTM_h uses the same hypothetical liquidation value but only for trades with duration > h.

## Outputs

For each B1..B5 and horizon:

- N with valid horizon value;
- cumulative exit probability;
- cumulative losing-exit probability;
- cumulative winning-exit probability;
- survival probability;
- mean and median realized-or-MTM bp;
- mean and median survivor-MTM bp;
- survivor count.

Also report by compression band:

- actual final mean net bp;
- actual fast-loss rate;
- two-sided-fast-loss rate where defined;
- actual mean duration.

## B5 vs B1 descriptive uncertainty

Using 20-trading-day calendar blocks of T0 signal bars, 5,000 resamples, seed 20260919, report at each horizon:

- Delta cumulative losing-exit probability = B5-B1;
- Delta realized-or-MTM mean bp = B5-B1;
- Delta survival probability = B5-B1.

These intervals are descriptive. No horizon is selected or promoted from this atlas.

## Boundary

No delayed-entry, confirmation, stop, size or exit rule is accepted here.

The atlas only identifies the time structure of the already-observed compression/fast-loss relationship.