# Two-Wave 8×native-5m delayed-causal wrapper V1 — equivalence audit and freeze

Issue #424.

## Status

`WRAPPER_FROZEN_RETROSPECTIVE_EQUIVALENT`

The delayed-causal wrapper is accepted as an exact time-alignment layer around the frozen current-band recognizer V1 retrospective oracle.

It does not alter the oracle.

## Frozen oracle

Oracle freeze merge commit:

`1eae26785c8faa1b93777d311ba172fc03422075`

Oracle freeze checkpoint SHA256:

`4b2f84d1c0d45a7e049a17866e907f97dfe0470f3fbcccf2cb3d5a8983204774`

Authoritative oracle source Git blob used for the isolated audit:

`476c8ff7687354213d4933cf3d853029d77fba8f`

Frozen weights:

`[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`

## Wrapper clock

At knowledge index `k`:

- target index = `k-8`;
- delay = 8 native 5m bars = 40 trading minutes;
- recognizer close window = `[k-63,k]`;
- amplitude high/low window = `[k-16,k]`;
- first eligible knowledge index = 63;
- first eligible target index = 55.

The implementation validates only causal slices through `k`. Future suffix values are not scanned before emission.

## Engineering tests

Focused wrapper tests:

`9 passed`

Coverage includes:

- first eligible endpoint;
- target/knowledge alignment;
- pre-eligible fail-closed behavior;
- synthetic direct-oracle equivalence;
- future-suffix invariance, including invalid future values;
- timestamp future-suffix invariance;
- exact batch row count;
- technical DATA_INVALID separation.

Wrapper source SHA256:

`9aa43cd917178942274fee84fa563bdc347852a7cd777ae12b78bc115ea79678`

Wrapper test SHA256:

`1644b81957d74eac447c0e224d9251ac716d3637392f9c742126a8e62d312023`

## Full Development equivalence audit

Audit source:

- previously consumed CSI1000 native 5m Development data;
- source SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`;
- source rows: 70,114;
- fresh OOS claim: false.

Eligible endpoint population was frozen before comparison:

`70,051`

Wrapper emitted rows:

`70,051`

Results:

- alignment mismatches: `0`;
- label mismatches: `0`;
- exact retrospective-oracle identity: `1.0`;
- deterministic full replay: byte-identical.

Prediction ledger SHA256:

`04039beeffe3479fb884c36fbe33458a648c22e223bced9f4290e44dc0cfd59c`

Audit receipt SHA256:

`b95de361aa06f8589cc35fcac5ad63e7c41567e37ad2960702d6da9e9172235c`

Wrapper freeze checkpoint SHA256:

`26115f697ac160b59d223b4ce5ae8dc0a3cf1d4227fb55a961cd08027b05141f`

## Acceptance

All preregistered wrapper conditions passed:

- output count exact;
- target/knowledge index alignment exact;
- exact label identity = 100%;
- mismatches = 0;
- future-suffix invariance passed;
- deterministic replay byte-identical.

Therefore V1 is frozen as the `8 × native 5m` retrospective-equivalent delayed-causal wrapper.

## Scope boundary

This result is an engineering identity result, not a new market-performance result.

It does not claim new OOS evidence and does not grant signal, trade, router, PnL-selection, paper/live or production authority.

The old 104-bar historical refill/backfill ceiling remains a different quantity and is not part of this wrapper acceptance.
