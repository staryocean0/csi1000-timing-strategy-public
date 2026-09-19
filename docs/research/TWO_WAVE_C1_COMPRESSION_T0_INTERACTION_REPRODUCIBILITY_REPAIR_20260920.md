# C1 compression × T0 interaction reproducibility repair

Date: 2026-09-20.

Historical study: Issue #571, `C1_COMPRESSION_T0_INTERACTION_NOT_SUPPORTED`.

## Problem found during Issue #615 replay

The tracked file:

`executor/two_wave_c1_compression_t0_interaction_v1.py`

contained Remote Desktop Commander read/execute wrapper text committed as source:

- a leading `[Reading 251 lines ...]` line plus its separator blank line;
- a trailing separator blank line plus `[executed on device: ...]`.

The tracked contaminated file SHA256 was:

`a56e27226a12befc45a5c92146fc11381042a5d58daea915b4ba1be2e8b10c94`.

It was not importable Python.
## Repair

Only the four wrapper/separator lines were removed.

No research logic, constant, estimator, bootstrap rule, threshold, or outcome code was changed.

After removing exactly those four lines, the module SHA256 is:

`d4abd95e4a81d5074a4e37cd695e054ccccb48c4b2a78bfece0e726bfc83393d`.

This is an exact match to the module SHA256 already recorded in:

`TWO_WAVE_C1_COMPRESSION_T0_INTERACTION_RESULT_20260919.json`.

The repaired file also passes Python bytecode compilation.

## Interpretation

This restores the historical #571 source to its already-declared exact module identity. It does not revise the #571 scientific result and does not grant any new authority.

Issue #615 does not depend on #571's module; it uses the underlying frozen causal-state and T0 trade primitives directly.
