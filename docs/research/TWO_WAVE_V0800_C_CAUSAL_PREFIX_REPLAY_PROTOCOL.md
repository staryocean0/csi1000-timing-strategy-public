# Two-Wave v0.8.0 — V0800-C causal prefix replay protocol

Status: frozen before the first V0800-C run.

## Purpose

V0800-C is a **causal-integrity test only**. It does not choose a same-scale threshold and it does not classify direction.

The B1 adjudication accepts literal shared-anchor `L-H-L-H-L` as the only direction-eligible continuity semantic for v0.8.0, keeps duration as the primary scale coordinate, and carries the four frozen candidate rho values `{1.25, 4/3, sqrt(2), 1.5}` without a winner.

The only question here is:

> At the end of every bar prefix, is the set of pivots, A-waves, strict pairs, channel geometry and same-scale eligibility exactly the set that was causally knowable at that moment?

## Input and kernel

Use only the already-consumed CSI1000 `5m_offset_0` Development input from 2015-01-05 through 2020-12-31 with the frozen file identity from V0800-B/B1.

Keep the v0.4.3 temporal-maturity kernel unchanged:

- `min_leg = 4` bar intervals;
- `max_unfinished_leg = 48` bar intervals;
- close-based extrema for causal pivot timing;
- native bar low/high values for frozen A-channel geometry;
- A-wave = `low -> high -> low`;
- strict pair = shared-anchor `low-high-low-high-low`.

No 2026 data is permitted.

## Two independent implementations

### Producer

The producer must implement an incremental state machine independently. It may reuse the frozen data loader and pure semantic primitives (`AWave`, channel geometry and same-scale relation), but it **must not import or call** `TemporalMaturityAEngine`.

At bar `i`, it may emit only events whose confirmation bar is exactly `i`.

It writes four append-only event ledgers:

- `PIVOT_EVENTS.csv`
- `RESET_EVENTS.csv`
- `WAVE_EVENTS.csv`
- `STRICT_PAIR_EVENTS.csv`

The strict-pair ledger records the duration ratio and four same-scale booleans. Legacy rho=2 is not evaluated in C.

### Independent verifier

The verifier uses the frozen `TemporalMaturityAEngine` as the reference implementation, runs it once over the same Development bars, derives the reference event ledgers, and compares them with the producer ledgers.

It must compare:

- event identities;
- occurrence and confirmation bars;
- epochs and censoring;
- A-wave pivot bars and frozen native prices;
- strict shared anchor;
- bottom-authoritative channel geometry;
- duration ratio;
- same-scale boolean under every frozen candidate rho.

The producer state machine and verifier reference engine therefore do not share the causal state-machine implementation.

## Why event equality proves every prefix

All accepted pivots, waves and pairs are append-only after confirmation. If the producer and independent reference have exactly the same event deltas at every confirmation bar, and no event is emitted before its confirmation bar, their cumulative knowledge sets are identical after every bar prefix.

This gives a prefix-by-prefix causal proof without an O(N²) rerun of the entire history for every prefix.

## Pass condition

V0800-C passes only if every mismatch count is zero and the independent verifier returns `status=passed`.

A pass proves causal availability only. It does **not**:

- select rho;
- add an amplitude gate;
- use tau or kappa;
- publish Range / UpTrend / DownTrend;
- read future returns;
- use PnL or positions;
- grant trading or production authority;
- authorize V0800-D automatically.

After C passes, rho reduction requires a separate preregistered adjudication before any direction grid.
