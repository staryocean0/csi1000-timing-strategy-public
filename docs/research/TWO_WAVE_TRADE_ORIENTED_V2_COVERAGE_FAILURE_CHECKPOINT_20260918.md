# Two-Wave trade-oriented V2 — coverage failure checkpoint

Issue #417 records why the first 368-panel pass pair is not allowed to enter final adjudication.

- packet: 368 panels / 368 unique trading days
- Pass A SHA256: `f52735bbfdd7de2021042019ad8b4c268ee0fe2711961c72a285d580d47bb37c`
- Pass B SHA256: `cf3d5cf33eb3b3d62eae24d6bf2ce60772bf31cdc1a905de40f06ff568702b98`
- A/B disagreements: 89
- both passes labeled FINER_SCALE_OUT_OF_BAND exactly 0 times
- full label-blind development audit found 998 amplitude-pass high-frequency targets with weak 4-bar current-band drift
- after excluding original packet days, 200 unique days remained available
- 32 deterministic FINER coverage challenges can be added (16 below Q50 amplitude, 16 at/above Q50)
- local coverage-failure checkpoint SHA256: `21addc3adbca31f7704b5f253350d154841c7f6c4b9ee85f7ddaa0a47cd624d1`

Verdict:

`COVERAGE_INSUFFICIENT_FAILED_PASSES`

The first V2 passes are preserved as failed evidence. They are not relabeled, deleted, or used as final reference labels. V2.1 must rerun both blind passes from scratch.

No old B0-B5 labels, future returns, PnL, recognizer outputs, or challenge identities were used to reach this verdict.
