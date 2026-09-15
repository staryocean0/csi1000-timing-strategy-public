# Two-Wave v0.8.0 — V0800-F operational state-stream audit

## Purpose

V0800-F is the next semantic gate after the V0800-E post-audit adjudication. It freezes the nominated morphology parameters and asks whether the resulting **causal event-time state stream itself** behaves coherently. It is not an outcome study and it is not another parameter search.

The frozen operational semantics are:

- strict continuity: `L0-H0-L1-H1-L2`;
- knowledge time: the current A-wave confirmation bar;
- same-level boundary: `rho=sqrt(2)`;
- one-wave Range dead-zone: `tau=0.20`;
- same-direction trend-speed tolerance: `kappa=2.00`;
- bottom-authoritative channel geometry, with the top line only a parallel translation.

The input remains the already-consumed CSI1000 `5m_offset_0` Development file for 2015-01-05 through 2020-12-31. V0800-F may not read 2026 data and may not substitute another dataset.

## Event stream

The producer emits exactly one row for every strict consecutive A-wave pair, in causal confirmation order. The temporal-level gate is applied first.

If a strict pair fails `rho=sqrt(2)`, its stream state is `ScaleIneligible`; it cannot publish Range or trend. If it passes the scale gate, the fixed `tau/kappa` classifier yields `Range`, `UpTrend`, `DownTrend`, or `Uncertain`.

Every strict pair is assigned exactly one reason:

- `scale_ineligible`;
- `both_range`;
- `same_up_within_kappa`;
- `same_down_within_kappa`;
- `sign_conflict`;
- `mixed_range_direction`;
- `speed_mismatch`.

This reason partition is descriptive morphology only. It contains no future market outcome.

## Overlap adjacency and hard invariant

Two consecutive strict-pair events are overlap-adjacent when the earlier event's `current_wave_id` is exactly the later event's `previous_wave_id`. This is the natural rolling two-wave stream:

`(A0,A1) -> (A1,A2)`.

Because `tau` is frozen, the shared A-wave `A1` has one and only one descriptor. Therefore the current descriptor of the first pair must equal the previous descriptor of the second pair.

A stronger consequence follows for published directional states. Direct overlap-adjacent transitions

- `UpTrend -> DownTrend`, or
- `DownTrend -> UpTrend`

are structurally impossible. Such a transition would require the shared middle A-wave to be both `UP` and `DOWN`. Any observed occurrence is a hard V0800-F failure, not a statistic to explain away.

Operational transition statistics are computed only when both overlap-adjacent pairs pass `rho=sqrt(2)`. A scale-ineligible pair breaks the operational run rather than being silently skipped.

## Required diagnostics

V0800-F reports the full strict-pair count and scale-eligible count, state and reason counts, annual 2015–2020 state/reason counts, overlap-adjacency counts, the fixed-state transition matrix, shared-descriptor mismatch count, forbidden direct-opposite transition count, same-state run-length histograms, and the fraction of eligible overlap transitions that change state.

Same-state run lengths are measured in **adjacent state events**, not bars. A run is broken by a non-overlap, a scale-ineligible event, or a change of state. This keeps persistence semantics tied to the causal state stream rather than wall-clock duration.

No numerical persistence or churn cutoff is invented in this protocol. Those quantities are diagnostic and require post-run semantic adjudication. The only automatic failures are violations of the frozen structural invariants or output/input identity.

## Independent verification

The trusted verifier must independently re-enumerate strict pairs from the frozen `TemporalMaturityAEngine`; it must not consume the producer's pair ledger as an authority. It independently recomputes `rho`, `g`, descriptors, reasons, states, overlap adjacency, transitions, run lengths, and all aggregate counts, then exact-compares the producer output.

The row-level event table is not mirrored as convenient private text. Only verified `SUMMARY.json` and `INPUT_RECEIPT.json` are mirrored after successful cleanup and private archive publication.

## Authority boundary

V0800-F uses no future return, PnL, position, cost, trade simulation, or 2026 data. It cannot change `rho`, `tau`, or `kappa`. It grants no direction acceptance, state-publication authority, trading authority, or production authority.

Even if all hard invariants pass, `state_stream_acceptance` remains unset until a separate post-run adjudication reviews persistence, churn, abstention reasons, and annual stability. Only after that separate gate could the project decide whether an outcome-bearing validation should even be preregistered.
