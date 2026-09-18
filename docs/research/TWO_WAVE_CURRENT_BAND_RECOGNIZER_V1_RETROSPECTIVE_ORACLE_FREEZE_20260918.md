# Two-Wave current-band recognizer V1 — retrospective oracle freeze

Issue #420.

## Status

`RETROSPECTIVE_ORACLE_FROZEN`

The trade-oriented current-band recognizer V1 is accepted as the retrospective oracle for the frozen V2.1 primary taxonomy.

This freeze is based on the one-time protected evaluation after the calibration weights were frozen.

## Frozen taxonomy target

Primary-label oracle SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

Primary states:

- CURRENT_UP
- CURRENT_RANGE
- CURRENT_DOWN
- LOW_AMPLITUDE_VETO
- FINER_SCALE_OUT_OF_BAND

## Frozen recognizer

Calibration freeze checkpoint SHA256:

`8f237fecc911ea01bdc324a51df61a30b7a843324d68ec117d2ea7dc35de0067`

Weights:

`[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`

Direction threshold remains `±0.20`.

LOW and FINER gates remain the preregistered fixed gates. No 128/256 context, date, stratum, outcome or PnL is used.

## One-time protected evaluation

Protected labels were opened once under the frozen protocol and then immediately returned to mode `000`.

Protected label SHA256:

`050aaaeed87240fad921be1496c8e38b6123971b96ebff7cbe9164f40b7f2478`

Protected rows: 78.

Support:

- CURRENT_UP: 29
- CURRENT_RANGE: 9
- CURRENT_DOWN: 31
- LOW_AMPLITUDE_VETO: 8
- FINER_SCALE_OUT_OF_BAND: 1

Exact identity:

`0.9487179487179487`

Macro recall:

`0.957533061426276`

Minimum state recall:

`0.8888888888888888`

Per-state recall:

- CURRENT_UP: `0.9310344827586207`
- CURRENT_RANGE: `0.8888888888888888`
- CURRENT_DOWN: `0.967741935483871`
- LOW_AMPLITUDE_VETO: `1.0`
- FINER_SCALE_OUT_OF_BAND: `1.0`

Per-state precision:

- CURRENT_UP: `0.9642857142857143`
- CURRENT_RANGE: `0.7272727272727273`
- CURRENT_DOWN: `1.0`
- LOW_AMPLITUDE_VETO: `1.0`
- FINER_SCALE_OUT_OF_BAND: `1.0`

Confusion matrix, rows=true and columns=prediction in state order UP/RANGE/DOWN/LOW/FINER:

```text
27 2  0  0  0
1  8  0  0  0
0  1 30  0  0
0  0  0  8  0
0  0  0  0  1
```

Deterministic replay: passed.

Protected evaluation receipt SHA256:

`db5ce56103bb5c34238a3cde2ca533552b96f1c5110ec9c872d66f3663e6fb63`

Row-level evidence SHA256:

`7bac0eb786b1454d09e4a75497dc95c2f394e8d8840a6d50f062570fde5783cf`

Retrospective oracle freeze checkpoint SHA256:

`4b2f84d1c0d45a7e049a17866e907f97dfe0470f3fbcccf2cb3d5a8983204774`

## Governance

Post-protected V1 retuning is forbidden.

Any future change to recognizer family, gates, direction coordinates, weights or thresholds requires a new recognizer version.

This freeze grants no signal, trade, router, PnL-selection, paper/live or production authority.

## Next phase

Begin the separate `8 × native 5m` delayed-causal retrospective-equivalent wrapper.

The wrapper is not allowed to change the frozen oracle. It may only emit, at knowledge bar `k`, the frozen oracle label for target bar `t=k-8` using exactly the same bars and preprocessing.

Wrapper acceptance requires 100% exact identity to the frozen retrospective oracle on all eligible endpoints.
