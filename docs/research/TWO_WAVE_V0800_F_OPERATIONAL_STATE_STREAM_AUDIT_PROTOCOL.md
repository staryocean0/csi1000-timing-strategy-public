# Two-Wave v0.8.0 — V0800-F operational state-stream audit

## Purpose

V0800-F is the next semantic gate after the verified V0800-E visual audit and its post-audit adjudication. It freezes the nominated morphology tuple `rho=sqrt(2)`, `tau=0.20`, `kappa=2.00` and asks a narrower question: **what event-time state sequence does this fixed definition actually produce at causal A-wave confirmation times?**

This is still Development morphology research. It does not use future returns, PnL, trading outcomes, 2026 data, or any other outcome-bearing information.

## Why the primary stream contains all 2,358 strict pairs

The rho rule makes only 924 strict consecutive pairs same-scale eligible. It would be misleading to delete the other strict confirmations and then join the 924 eligible events as though they were always adjacent. Two eligible states can have one or more scale-mismatch strict pairs between them.

Therefore the primary event stream contains every strict `L-H-L-H-L` pair confirmation in causal order. Each event receives exactly one label:

- `Range`, `UpTrend`, `DownTrend`, or `Uncertain` if the pair satisfies `rho=sqrt(2)`;
- `NoStateScaleMismatch` if it does not.

`NoStateScaleMismatch` is deliberately distinct from `Uncertain`. `Uncertain` means the pair is same-scale but the frozen direction/speed morphology does not support a state. `NoStateScaleMismatch` means the pair was never eligible to form a two-wave state at this scale.

## Event time is not bar time

F does **not** install a carry-forward rule. A state exists only as the label of a causal confirmation event. Between confirmation events the bar-time state is undefined. The study must not silently hold the last event state until the next event.

This separation is intentional: first audit the event-time state machine; only a later preregistered gate may decide whether and how an accepted event state persists across bars.

## Reset and continuity rule

Transitions and run lengths never cross a pivot-engine reset/epoch boundary. Within an epoch, primary events are ordered by `(epoch, confirmation_bar, pair_id)`.

The study also reports an eligible-only sequence as a secondary diagnostic, but every eligible-to-eligible step must carry the number of intervening strict events. That secondary sequence cannot erase scale-mismatch gaps or claim bar-time continuity.

## Frozen state rule

For each A-wave, `g` remains normalized bottom migration in channel-height units. With `tau=0.20`:

- `RANGE` if `|g| <= 0.20`;
- `UP` if `g > 0.20`;
- `DOWN` if `g < -0.20`.

For an eligible pair, let `r=max(|g_prev|,|g_cur|)/min(|g_prev|,|g_cur|)`. With `kappa=2.00`:

- both `RANGE` -> `Range`;
- both `UP` and `r<=2` -> `UpTrend`;
- both `DOWN` and `r<=2` -> `DownTrend`;
- every other eligible case -> `Uncertain`.

A duration ratio above `sqrt(2)` bypasses this four-state rule and becomes `NoStateScaleMismatch`.

## Diagnostics

The row-level event ledger remains private. Aggregate output reports state counts and annual counts, within-epoch transition matrices for the full strict stream and the eligible-only diagnostic stream, event-label run lengths, eligible confirmation-gap quantiles, counts of intervening strict events between eligible confirmations, and direct `UpTrend <-> DownTrend` reversals.

These are morphology/sequence diagnostics only. There is no automatic pass/fail threshold based on state balance, coverage, persistence, reversal frequency, or abstention frequency. The run requires a separate post-run adjudication.

## Hard boundaries

V0800-F does not search `rho`, `tau`, or `kappa`. It does not read 2026, future returns, PnL, positions, costs, or subsequent market outcomes. It does not simulate trades. It grants no direction acceptance, state-publication authority, trading authority, or production authority.

If the fixed event stream exposes a semantic pathology, the project returns to morphology design. If it is coherent, a later separately preregistered gate may define bar-time carry-forward semantics before any outcome-bearing validation.
