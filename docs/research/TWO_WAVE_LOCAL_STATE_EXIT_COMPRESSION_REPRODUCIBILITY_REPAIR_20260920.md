# Issue #624 scored-ledger reproducibility repair

Date: 2026-09-20.

Status: `EVIDENCE_SERIALIZATION_REPAIR_ONLY__10G_REPLAY_PENDING`.

## Trigger

The first governed run for issue #624, public run `35487560301`, reproduced the same scientific result as local execution:

- same 29,713 scored rows;
- same 38 bootstrap blocks;
- same pooled/year/state metrics;
- same bootstrap intervals;
- same support checks;
- same two failed information gates;
- same final verdict:
  `LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`.

The independent verifier passed.

However, private readback showed that the CSV evidence artifact had a different SHA256 from the local replay.

## Root cause

A field-by-field comparison found no scientific-value drift.

The exact-result JSON differed only because it embeds `scored_ledger_sha256`.

The original full-precision ledgers differed in only 8 of 29,713 rows and only in raw floating-point feature cells at platform/libm last-bit scale:

- `abs_ret_8`: maximum absolute difference about 1.8e-15;
- `rv_8`: maximum absolute difference about 3e-16;
- `efficiency_8`: maximum absolute difference about 2.5e-13.

All discrete states, targets and risk bands were identical. Compression scores, aggregate statistics, bootstrap intervals and the verdict were identical.

Therefore the discrepancy is an evidence-byte serialization issue, not a scientific-result discrepancy.

## First repair attempt: 11 significant digits

The first repair canonicalized the written CSV with:

`to_csv(..., float_format="%.11g")`.

Local Python 3.11 replay passed and produced:

- ledger SHA256 `6fb0d646445fc8c5d7ebc0f664681144b2fd2c8fc72b85758c7bf28e1cf9015b`;
- exact-result SHA256 `d4819aa079fec652ccb7ff8e19f2241958e5f2469fd8f2a99fe71287cd3834db`.

Governed replay `35488173033` again reproduced the same scientific result and independent-verifier PASS, but private readback exposed one remaining cross-runtime serialized-cell difference:

- one `rv_8` value serialized as `0.00089452054366` locally;
- the same scientific value serialized as `0.00089452054367` on the governed runner.

Thus 11 significant digits were still one digit too fine for byte-stable cross-runtime evidence.

Run `35488173033` remains immutable historical evidence and is marked non-canonical only at the byte-serialization layer.

## Final repair candidate: 10 significant digits

No feature computation, score, band, target, bootstrap, threshold, gate or verdict is changed.

Only the written evidence representation is canonicalized to:

`to_csv(..., float_format="%.10g")`.

The independent verifier reconstructs the full-precision scientific values, canonicalizes them to the same 10-significant-digit representation, and requires exact equality to the serialized ledger.

The original full-precision local ledger and the first governed full-precision ledger from run `35487560301` were independently re-canonicalized to 10 significant digits. All 29,713 rows then became byte-identical. The already-rounded 11g artifact from run `35488173033` is not used as proof of 10g identity because re-rounding an already-rounded artifact can introduce double-rounding effects.

A fresh reviewed Python 3.11 replay using the 10g runner/verifier produced:

- canonical ledger SHA256:
  `c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f`;
- canonical exact-result SHA256:
  `0760393f9a27b4a7db2ad65a931e449c68ca71c2aeba7a657867d9929743519b`;
- independent verifier: PASS;
- verified rows: 29,713;
- verified blocks: 38;
- verdict unchanged:
  `LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`.

Ten significant digits remain far finer than any frozen issue-624 decision threshold and are used only for evidence serialization, never for score construction or adjudication.

## Historical handling

Both earlier governed runs remain immutable:

1. `35487560301`: full-precision CSV, scientifically identical, byte-noncanonical;
2. `35488173033`: 11g CSV, scientifically identical, one serialized cell still byte-noncanonical.

Neither run is relabeled as a scientific failure.

A new governed replay is required after the 10g repair. Only a run whose private readback exactly matches the 10g canonical ledger/result SHA may close the reproducibility issue.

## Authority

No signal/router/trade/paper/live/production authority.
