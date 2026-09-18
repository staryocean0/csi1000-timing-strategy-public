# Two-Wave 8×native-5m delayed-causal wrapper V1 — preregistration

Issue #424. This phase starts only because the current-band recognizer V1 retrospective oracle is frozen and merged.

Oracle freeze merge commit:

`1eae26785c8faa1b93777d311ba172fc03422075`

Oracle checkpoint SHA256:

`4b2f84d1c0d45a7e049a17866e907f97dfe0470f3fbcccf2cb3d5a8983204774`

## Purpose

The wrapper is a time-alignment layer only.

It must not create, repair, reinterpret or recalibrate the frozen five-state recognizer.

At knowledge bar index `k`, it emits the frozen retrospective-oracle label for target bar:

[
t = k - 8
]

where one native bar is 5 minutes.

Therefore the fixed confirmation delay is exactly:

`8 × native 5m = 40 trading minutes`.

## Information boundary

For knowledge index `k`, the wrapper may read only bars with index `<= k`.

The frozen recognizer consumes:

- 64 native 5m close bars ending at `k`: `[k-63, k]`;
- 17 native 5m high/low bars for target `t=k-8`: `[t-8,t+8] = [k-16,k]`.

No 128/256 context is allowed.

No date/year, challenge stratum, old taxonomy, outcome, return or PnL is allowed.

No bar `k+1` or later may affect the output emitted at `k`.

## Eligibility

A wrapper endpoint is eligible when:

- `k >= 63`;
- required 64-bar current-band history is present;
- required 17-bar amplitude window is present;
- all required OHLC values are finite and positive;
- timestamps, if supplied, are already unique and increasing.

The first emitted target is therefore `t=55`.

A batch replay over `N` valid native bars must emit exactly:

`max(0, N-63)`

rows, one for each knowledge index `63..N-1`.

## Frozen oracle parameters

Weights:

`[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`

Direction threshold:

`±0.20`

LOW and FINER gates are imported unchanged from current-band recognizer V1.

The wrapper may call the recognizer but may not duplicate it with modified semantics.

## Required wrapper output

Each eligible emitted row must contain at minimum:

- `knowledge_index = k`;
- `target_index = k-8`;
- `delay_bars = 8`;
- `label`;
- if timestamps are supplied: exact target timestamp and knowledge timestamp.

The wrapper must not pretend the label was known at target time. The knowledge index/timestamp is part of the contract.

## Retrospective-equivalence audit

For every eligible endpoint `k` in the audit population:

1. call the wrapper using only prefix data through `k`;
2. separately call the frozen retrospective oracle using exactly the 64/17-bar windows ending at `k`;
3. compare labels exactly.

Acceptance requires:

- eligible endpoint count fixed before comparison;
- wrapper output count exact;
- target/knowledge index alignment exact;
- exact label identity = `1.0`;
- mismatches = `0`;
- deterministic replay byte-identical.

No tolerance, score distance or majority agreement is accepted.

## Causality tests

Required tests include:

- appending arbitrary future suffix bars after knowledge index `k` cannot alter the emitted row at `k`;
- changing a bar before or at `k` is allowed to alter the result;
- a wrapper call at `k` cannot request data beyond `k`;
- first eligible index and final endpoint are correct.

## Audit population

The initial formal engineering equivalence audit uses the full previously consumed 2015–2020 native 5m Development file already used by the oracle work.

This is **not** new scientific OOS evidence. It is an implementation identity audit.

The full eligible endpoint population is used, not only the 400 frozen reference panels.

## Distinction from historical refill bounds

The wrapper's eight-bar confirmation delay is a fixed endpoint knowledge allowance.

It must not be compared with or described as the old 104-bar whole-history refill/backfill ceiling. Those quantities answer different questions.

## Stop rule

Any mismatch blocks wrapper acceptance.

A mismatch is repaired only as an implementation/alignment defect. The frozen oracle may not be changed to make the wrapper pass.

## Authority

Even 100% wrapper equivalence grants no signal, trade, router, PnL-selection, paper/live or production authority.
