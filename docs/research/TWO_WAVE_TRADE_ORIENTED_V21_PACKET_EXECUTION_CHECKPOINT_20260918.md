# Two-Wave trade-oriented V2.1 blind packet — execution checkpoint

Issue #417. Parent packet issue #415.

## Prior V2 packet status

The first 368-panel packet and its two sealed passes are preserved as:

`COVERAGE_INSUFFICIENT_FAILED_PASSES`

They are not eligible for final adjudication.

- old Pass A SHA256: `f52735bbfdd7de2021042019ad8b4c268ee0fe2711961c72a285d580d47bb37c`
- old Pass B SHA256: `cf3d5cf33eb3b3d62eae24d6bf2ce60772bf31cdc1a905de40f06ff568702b98`
- coverage failure checkpoint SHA256: `21addc3adbca31f7704b5f253350d154841c7f6c4b9ee85f7ddaa0a47cd624d1`

## V2.1 packet

Local evidence root:

`csi1000-reference-review-evidence/trade-oriented-taxonomy-v21-20260918-v1`

Verified counts:

- total panels: 400
- unique panel IDs: 400
- unique trading days: 400
- PRIMARY: 240
- LOW_AMPLITUDE: 32
- NEAR_VETO: 32
- HF_LOW_NORMAL_AMP: 32
- HF_HIGH_AMP: 32
- FINER_DOMINANT_LOW_NORMAL_AMP: 16
- FINER_DOMINANT_HIGH_AMP: 16
- primary SVG: 400
- context128 SVG: 400
- context256 SVG: 400
- manifest entries: 1200
- manifest mismatches: 0

The two added FINER coverage halves both use previously unused trading days and both remain label-blind sampling strata.

## Blind contract

Blind inventory contains only:

- `panel_id`
- `amplitude_gate`

It does not expose dates, target indices, strata, numeric amplitude, subband score, old labels, recognizer outputs, outcomes or PnL.

The 128/256 context directories remain physically separate and forbidden during the new primary passes.

## Frozen identities

- controlled inventory SHA256: `550eaea28a43d099c4241c84cf7fa04d3b8991a3ecfedb12847f282ce1bc8328`
- blind inventory SHA256: `31dbf3fb03a232f5b4d25f31a670eba5f84b00cfa305250d17cab208998cc58a`
- panel manifest SHA256: `e9227543421ae2243f5bda6845eedf6db9b877ad55e831e34cc1336cbcc3c858`
- packet summary SHA256: `df95117b99632295786f3e6d4f45fed9ef17477c3ac97df981fa39c43d57b6b1`
- packet file-hash ledger SHA256: `b06e7cfc2fe23a36e064da2f99c35be92069195ed4afb4c9d16aafc5812f4dc7`

## Status

`V21_BLIND_PACKET_READY_NEW_PASSES_NOT_STARTED`

V2.1 must run both primary passes from scratch. No label from the failed 368-panel passes may be copied into the new pass files.
