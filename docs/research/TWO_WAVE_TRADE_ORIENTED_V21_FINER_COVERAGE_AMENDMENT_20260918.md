# Two-Wave trade-oriented taxonomy V2.1 — FINER coverage amendment

Issue #417. Parent packet issue #415; taxonomy parent #409.

## Why V2.1 is required

The first 368-panel V2 packet completed two sealed primary-only blind passes.

Both passes produced zero `FINER_SCALE_OUT_OF_BAND` labels.

That result was not accepted as evidence that the state does not exist, because the original HF challenges only required local high-frequency alternation. They did not require the current-band projection itself to weaken.

A label-blind coverage audit over the full already-consumed development interval found:

- eligible targets: 69,851;
- amplitude-pass + high-frequency candidates: 51,039;
- high-frequency candidates with weak 4-bar current-band recent and full drift: 998;
- after excluding all 368 packet trading days: 200 unique eligible trading days.

Therefore the original packet did not sufficiently attack the intended FINER mechanism.
## Status of the first V2 passes

The original packet and both passes remain immutable evidence.

They are classified as:

`COVERAGE_INSUFFICIENT_FAILED_PASSES`

They must not be adjudicated into final five-state labels.

Frozen failed-pass identities:

- Pass A SHA256: `f52735bbfdd7de2021042019ad8b4c268ee0fe2711961c72a285d580d47bb37c`
- Pass B SHA256: `cf3d5cf33eb3b3d62eae24d6bf2ce60772bf31cdc1a905de40f06ff568702b98`
- A/B disagreement rows: 89
- disagreement ledger SHA256: `e70e47acdb51906fccd693dd9123708e7ea2eae81eb09f361c1f50132394b900`
- coverage-failure checkpoint SHA256: `21addc3adbca31f7704b5f253350d154841c7f6c4b9ee85f7ddaa0a47cd624d1`

No old taxonomy labels, outcome, return or PnL were used in the coverage audit.
## Label-blind FINER coverage metric

For each amplitude-pass target, use the same 64-bar primary close path ending at t+8.

Split the 64 log-close bars into sixteen consecutive four-bar blocks and compute each block mean.

Define:

- `range_ratio = range(block_means) / range(raw_64)`;
- `tv_ratio = TV(block_means) / TV(raw_64)`;
- `residual_fraction = MSE(raw_64 - repeated_block_mean) / MSE(raw_64 - mean(raw_64))`;
- `recent_abs_drift` = absolute normalized linear drift of the last eight block means;
- `full_abs_drift` = absolute normalized linear drift of all sixteen block means.

Candidate eligibility additionally requires:

- frozen amplitude veto passes;
- the FINER target neighborhood is the 24 native-5m bars `[t-15,t+8]`;
- within that 24-bar neighborhood, return-sign changes >= 9;
- within that 24-bar neighborhood, median same-sign run length <= 2 bars;
- `recent_abs_drift < 0.25`;
- `full_abs_drift < 0.25`.

The 24-bar neighborhood is deliberately different from the 17-bar amplitude window. The former is a frequency-coverage diagnostic; the latter remains the frozen local actionability metric.

Coverage score:

[
S_{subband}
=
(1-range_ratio)
+
(1-tv_ratio)
+
residual_fraction.
]

This score is used only for challenge sampling. It is not a final state classifier.
## Added V2.1 challenge

Keep all original 368 panels unchanged.

Add 32 panels from trading days unused by the original packet:

- 16: `Q5 <= A_local_bps < Q50`;
- 16: `A_local_bps >= Q50`.

Within each amplitude half:

1. retain only the label-blind candidate mechanism above;
2. retain the highest-score target per trading day;
3. sort by `S_subband` descending;
4. take the first 16.

The deterministic dry-run selection produced 32 unique trading days and is frozen by selection SHA256:

`f7a072eebc72058399b726d296edd0fdac4d62341d79e9c1f5ac01c68ca6703c`.

## New packet cardinality

- original panels: 368;
- added FINER coverage panels: 32;
- V2.1 total: 400;
- required unique trading days: 400.

The new packet must rerun Pass A and Pass B from scratch.

Old Pass A/B labels may not be copied into the V2.1 pass files even for the original 368 panels.
## Annotation semantics remain unchanged

This amendment changes only coverage sampling.

The primary five states remain:

- CURRENT_UP
- CURRENT_RANGE
- CURRENT_DOWN
- LOW_AMPLITUDE_VETO
- FINER_SCALE_OUT_OF_BAND

Current-band identity still has priority.

A FINER challenge panel is **not automatically FINER**. If a valid current-band wave exists, it must still be labeled CURRENT_UP/RANGE/DOWN.

The challenge exists only to ensure the reference process actually sees the hardest candidate mechanism.

## Authority

No signal, routing, PnL-selection, paper/live or production authority is added.
