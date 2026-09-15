# Risk Tool V2 Phase-1b carrier reconciliation — 2026-09-15

## Purpose

Resolve the outstanding identity/counting contradiction between the frozen `data/index/5m_offset_0.parquet` inventory (`rows=135682`) and the user-delivered 5-minute bar receipt (`rows_total=148080`) before `INPUT_IDENTITY_FREEZE`.

This is an append-only extension of `risk-v2-phase1b-carrier-inventory-v1`. The original v1 broker and private mirror are preserved byte-for-byte as `*_core_v1.py`; the original `risk_phase1b_carrier_inventory.json` schema and candidate scope are unchanged.

## Authorized evidence

The reconciliation reads only the fixed handoff bundle already pinned by the v1 profile. In addition to the existing raw-byte inventory, it may read the frozen DataHub source contract:

- bundle member: `data/index/SOURCE_MANIFEST.json`
- bytes: `52711`
- SHA256: `c46f2da6c3df016ca054e183e37267dc472097450fcdd6644c22aa0084c15749`
- provenance: migrated from `factorlab_unified_index_kline_v3_20260824/manifest.json` as the DataHub source contract

The sidecar extracts only whitelisted identity/provenance fields from manifest objects associated with `5m_offset_0.parquet` or its frozen source/target hashes. Keys associated with prices, OHLC values, returns, labels, volume/amount, predictions, scores or PnL are rejected or omitted.

## Frozen comparison anchors

`data/index/5m_offset_0.parquet`:

- bytes: `3615731`
- target SHA256: `211448c914b547232bc536da7df94dc5ae279b8265a5cafe58409238485217d7`
- Git blob SHA1: `1005a95563795ff836d21efa29e417adfa9b3f65`
- source SHA256: `d3101e6adf7a3e85b11f7c3503a6161f3ab363f7edd90ac8cba451ffe409c46a`
- frozen rows: `135682`
- frozen date range: `2015-01-05` through `2026-08-21`
- transformation: `symbol filter only; original fields and legacy wallclock labels preserved`

User receipt constraints:

- `000688.SH`: rows `70848`, valid `66373`, first day `2020-07-23`, last day `2026-08-21`
- `000852.SH`: rows `77232`, valid `72358`, first day `2020-01-02`, last day `2026-08-21`
- total rows: `148080`

## Controls

The reconciliation sidecar must keep all of the following false:

- `year_2026_semantic_read`
- `parquet_deserialization`
- `price_return_label_columns_read`
- `model_fit`
- `confirmatory_scoring`
- `new_training`
- `production_authority`

No evaluator activation, calibration change, gate change, fresh-OOS scoring, PnL computation, or production routing is authorized by this change.

## Decision rule

The sidecar is evidence for reconciliation only. It does **not** itself complete `USER_DATA_CARRIER_BINDING` or authorize `INPUT_IDENTITY_FREEZE`. Those steps may advance only after the source-contract evidence explains whether `135682` and `148080` are different counting/selection views of the same delivered carrier or identify distinct carriers.
