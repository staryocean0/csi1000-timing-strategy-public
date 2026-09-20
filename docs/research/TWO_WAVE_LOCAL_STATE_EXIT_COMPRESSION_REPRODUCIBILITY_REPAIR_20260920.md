# Issue #624 scored-ledger reproducibility repair

Date: 2026-09-20.

Status: `EVIDENCE_SERIALIZATION_REPAIR_ONLY`.

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

The scored ledgers differed in a handful of raw floating-point feature cells at last-bit / libm scale, for example:

- `abs_ret_8`: about 1.8e-15 absolute difference;
- `rv_8`: about 3e-16;
- `efficiency_8`: at most about 2.5e-13.

Risk percentiles, compression scores, bands, outcomes, all aggregate statistics and the verdict were identical.

Therefore the discrepancy is an evidence-byte serialization issue, not a scientific-result discrepancy.

## Repair

No feature computation, score, band, target, bootstrap, threshold, gate or verdict is changed.

Only the written scored-ledger CSV is canonicalized:

- pandas `to_csv(..., float_format="%.11g")`;
- the independent verifier reconstructs the unrounded scientific values, canonicalizes them to the same written representation, and requires exact numeric equality to the serialized ledger.

The exact result continues to contain the SHA256 of that canonical ledger.

## Why 11 significant digits

Cross-runtime replay of the two already-produced ledgers showed that 12+ significant digits still preserved isolated platform-level last-bit differences, while 11 significant digits made all 29,713 rows byte-identical.

Eleven significant digits remain far finer than any frozen issue-624 decision threshold and are used only for evidence serialization, never for score construction or adjudication.

## Historical handling

Run `35487560301` remains immutable historical evidence.

It is not relabeled as a scientific failure. Its scientific content is accepted as matching local replay, while its scored-ledger bytes are marked non-canonical.

A new governed run is required after this repair. Only the post-repair run may be used as the canonical byte-reproducible controlled receipt for issue #624.

## Authority

No signal/router/trade/paper/live/production authority.
