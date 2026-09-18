# Two-Wave current-band recognizer V1 — protected evaluation protocol

Issue #420. This protocol is frozen **before** the 78 protected labels are opened.

## Frozen recognizer

Target oracle SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

Calibration freeze checkpoint SHA256:

`8f237fecc911ea01bdc324a51df61a30b7a843324d68ec117d2ea7dc35de0067`

Frozen weights:

`[0.5375062131339785, 0.02424630935968975, 0.2550411892804524, 0.08498791874772484, 0.0982183694781545]`

The model family, gates, coordinates and ±0.20 direction threshold are immutable for this evaluation.

## One-time opening rule

The protected file contains 78 rows.

Before evaluation it must be permission mode `000`.

A single evaluation process may:

1. change permission only long enough to read the file once;
2. read the protected bytes exactly once;
3. immediately return the original protected-label file to mode `000`;
4. evaluate the frozen recognizer;
5. persist a sealed evaluation receipt and row-level evaluation evidence.

No parameter or threshold may change after this read.

## Frozen protected acceptance gate

The protected evaluation is accepted only if **all** are true:

- LOW_AMPLITUDE_VETO recall = 1.0;
- FINER_SCALE_OUT_OF_BAND recall = 1.0;
- five-state exact identity >= 0.80;
- macro recall >= 0.75;
- no primary state has recall below 0.60;
- deterministic replay with the same frozen weights is byte-identical at the prediction level.

These are the same minimum semantic/quality gates used to permit progression from calibration.

No class may be dropped from macro recall because its protected support is small.

## Required report

Report:

- protected row count and per-state support;
- exact identity;
- confusion matrix;
- per-state recall and precision;
- LOW/FINER exactness;
- deterministic replay result;
- final verdict: `ACCEPT_V1_RETROSPECTIVE_ORACLE` or `REJECT_V1`.

A rejection opens a new recognizer version; it does not reopen V1 tuning.

## Wrapper boundary

Even an accepted retrospective recognizer does not yet authorize the delayed wrapper.

Only after V1 is accepted and frozen as the retrospective oracle may the separate `8 × native 5m` retrospective-equivalent wrapper phase begin.

No signal, trade, router, PnL-selection, paper/live or production authority is granted.
