# Two-Wave delayed-causal retrospective-equivalent wrapper V1 — acceptance freeze

Issue #425.

## Final verdict

`ACCEPT_WRAPPER_V1`

The fixed `8 × native 5m` delayed-causal wrapper reproduces the frozen current-band retrospective oracle exactly on every preregistered eligible endpoint of the fixed full development replay.

This is an engineering equivalence result. It does not add or change any market-state semantics.

## Frozen retrospective oracle

Primary taxonomy oracle SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

Protected evaluation receipt SHA256:

`db5ce56103bb5c34238a3cde2ca533552b96f1c5110ec9c872d66f3663e6fb63`

Accepted frozen direction weights:

`[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`

No oracle parameter, threshold, gate or taxonomy label was modified by the wrapper phase.
## Wrapper clock

At native-5m knowledge bar `k`:

- target is exactly `t = k - 8`;
- first eligible `k = 63`;
- 64-bar oracle close view is `[k-63, k]`;
- 17-bar amplitude window is `[k-16, k] = [t-8, t+8]`;
- no bar after `k` may be read;
- invalid required technical evidence fails closed to `DATA_INVALID`;
- an emitted target is never revised later.

The accepted frozen oracle is bound through `recognize_frozen(...)`.

## Fixed full replay

Source rows:

`70,114`

Source SHA256:

`bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Preregistered eligible endpoints:

`70,051`

Index range:

- first known index: `63`
- last known index: `70,113`
- first target index: `55`
- last target index: `70,105`
## Exact equivalence result

Wrapper rows:

`70,051`

Direct frozen-oracle rows:

`70,051`

Mismatch count:

`0`

Exact label identity:

`1.0`

Additional exact contracts:

- target sequence equality: passed
- `known_from = target + 8`: passed for every row
- evidence start `= known_from - 63`: passed for every row
- amplitude start `= known_from - 16`: passed for every row
- complete row equality to direct comparator: passed

Row-level wrapper evidence SHA256:

`379eacf2f276c1325fce125f844a069ab608f09efde663f31a850bebc056486f`

Full replay receipt SHA256:

`c567fdd7c05001237fa5820a8486855e79b2750fa40acb1e1b48034718b6ef01`
## Determinism and causality

A second full wrapper replay produced byte-identical row evidence.

Deterministic byte replay:

`true`

A long-prefix causality audit used known index `35,000`.

All `34,938` rows already emitted by that point were compared against a replay in which every later price bar was deterministically altered.

Prefix equality:

`true`

Therefore changing the suffix after the current knowledge boundary did not alter any already-emitted wrapper row.

## Tests

Focused recognizer + wrapper test suite:

`20 passed`

The tests cover:

- first eligible emission
- exact eight-bar delay
- direct-oracle identity
- prefix causality
- deterministic replay
- fail-closed technical validity
- input validation
- direct-oracle indexing
- explicit mismatch detection
- frozen-oracle binding

## Interpretation

The project now has:

1. a frozen five-state current-band taxonomy;
2. an accepted frozen retrospective recognizer;
3. an accepted `t+8` delayed-causal wrapper that is exactly retrospective-equivalent on the full fixed replay.

This result does **not** mean that the market labels themselves are universally perfect and does not establish profitability.

It means only that the online delay wrapper introduces no additional classification discrepancy relative to the frozen oracle.

## Authority

No R4, strategy selection, signal, trade, router, PnL-selection, paper trading, live trading or production authority is granted by this freeze.
