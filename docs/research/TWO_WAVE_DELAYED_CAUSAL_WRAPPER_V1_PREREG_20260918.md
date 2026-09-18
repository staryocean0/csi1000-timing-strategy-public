# Two-Wave delayed-causal retrospective-equivalent wrapper V1 — preregistration

Issue #425.

## Purpose

Wrap the frozen current-band recognizer V1 in a streaming/native-5m clock without changing its semantics.

The wrapper is successful only if its delayed online output is exactly the same as calling the frozen retrospective oracle directly on the same bounded evidence.

## Frozen oracle authority

- V2.1 primary taxonomy final-label SHA256:
  `bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`
- protected evaluation receipt SHA256:
  `db5ce56103bb5c34238a3cde2ca533552b96f1c5110ec9c872d66f3663e6fb63`
- retrospective oracle freeze checkpoint SHA256:
  `4b2f84d1c0d45a7e049a17866e907f97dfe0470f3fbcccf2cb3d5a8983204774`
- frozen weights:
  `[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`
- direction threshold: `±0.20`
- LOW and FINER gates: frozen V1 gates

No oracle parameter is fitted or selected in this phase.

## Clock contract

Native source bars are indexed by `k = 0,1,2,...`.

At knowledge bar `k`:

- if `k < 63`, emit nothing;
- otherwise target is exactly `t = k - 8`;
- the oracle close view is exactly bars `[k-63, k]`, 64 native 5m bars;
- the frozen amplitude window is exactly bars `[k-16, k]`, equivalent to `[t-8,t+8]`;
- no bar with index `> k` may be read.

The wrapper may carry timestamps/indices as metadata, but they are not classifier features.

## Technical validity

The generic wrapper accepts a per-bar technical-validity flag.

For target `t=k-8`, `technical_valid` passed into the frozen recognizer is:

`all(valid[k-63:k+1])`.

This is fail-closed. Invalid required evidence yields the recognizer's separate `DATA_INVALID` status.

The fixed development replay source used for equivalence audit has already-validated finite positive OHLC and increasing unique timestamps, so every replay endpoint is technically valid.

## Streaming API

Each pushed native 5m bar contains at minimum:

- high
- low
- close
- technical_valid

When enough history exists, return one immutable record containing:

- target_index = k-8
- known_from_index = k
- evidence_start_index = k-63
- amplitude_start_index = k-16
- label

The wrapper may not revise an emitted target later.

## Direct-oracle comparator

For every eligible `k`, direct oracle comparison uses the exact same:

- close64 = closes[k-63:k+1]
- highs17 = highs[k-16:k+1]
- lows17 = lows[k-16:k+1]
- technical_valid = all(valid[k-63:k+1])
- frozen weights

The comparator is not allowed to use the wrapper's output to construct its oracle input.

## Fixed full replay audit

Source:

- historical role: already-consumed development evidence
- file: native 5m offset-0 source
- rows: `70,114`
- source SHA256:
  `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Eligible knowledge endpoints are fixed before execution:

- first `k = 63`
- last `k = 70,113`
- eligible endpoints = `70,051`
- first target `t = 55`
- last target `t = 70,105`

No date/year/challenge/outcome/PnL filter is applied.

A secondary audit may report the 400 frozen V2.1 reference-panel targets as a subset, but it is not a substitute for the 70,051-endpoint full replay.

## Acceptance

All conditions must pass:

1. wrapper row count = 70,051;
2. direct-oracle row count = 70,051;
3. exact target-index sequence equality;
4. exact known-from relation `known_from = target + 8` for every row;
5. exact label identity = `70,051 / 70,051 = 100%`;
6. mismatch count = 0;
7. a second replay produces byte-identical row-level wrapper evidence;
8. prefix causality test confirms adding/changing a suffix after `k` cannot alter any already-emitted row.

Any mismatch rejects wrapper V1.

## Governance

This is equivalence engineering only.

No signal, trade, router, PnL-selection, parameter selection, paper/live or production authority is granted.
