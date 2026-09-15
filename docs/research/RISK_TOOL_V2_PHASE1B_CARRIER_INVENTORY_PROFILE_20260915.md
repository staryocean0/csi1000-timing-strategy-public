# Risk Tool 2.0 Phase-1b — User Data Carrier Inventory Profile

Date: 2026-09-15

Profile: `risk-v2-phase1b-carrier-inventory-v1`

Purpose: resolve `USER_DATA_CARRIER_BINDING` without consuming 2026 market semantics. The profile reads only the immutable handoff archive identity, `BUNDLE_MANIFEST.json`, and raw bytes of narrowly matched candidate files in order to compute byte hashes / Git blob SHA-1 identities.

## Frozen source

- Private authority base ref: `6f41091f1d29c5d6a3aaf74c49f538526c567eef`
- Private release tag: `csi1000-handoff-v1-20260913`
- Compressed archive SHA256: `1976161b108346603561dac0075e435e346892f66f049a3fe194c981c3fc3282`
- Recombined `bundle.tar` SHA256: `1c1e737e8d97d0b01bcc696e1893e70d017e926043062e913d06d64d2cc454ad`

The 20 immutable transport parts are frozen in `executor/risk_phase1b_carrier_inventory_profile.json`.

## Allowed candidate scope

Only archive members whose path ends with one of the following fixed suffixes may be opened for raw identity hashing:

- `data/market/5m/000688.SH/2026.parquet`
- `data/market/5m/000852.SH/2026.parquet`
- `bar_receipts.csv`
- `5m_offset_0.parquet` through `5m_offset_4.parquet`

The output may contain only role, archive path, bytes, SHA256 and Git-blob SHA1 for matched members, plus fixed archive / manifest identities and non-semantic control flags.

## Explicit prohibitions

This profile MUST NOT:

- deserialize parquet or inspect parquet schema / row values;
- read price, return, state, label or outcome columns;
- fit or refit parent models or Platt calibration;
- score the 2026 confirmatory cohort;
- change horizons, gates, bootstrap, clipping, symbols or cohort semantics;
- fetch a new market-data source;
- grant strategy, PnL, routing or production authority.

`year_2026_semantic_read=false` remains true after this inventory run.

## Success meaning

Runner success means only that archive membership and matched candidate byte identities were inventoried and privately written back through the broker. `BYTE_CANDIDATES_IDENTIFIED` is not yet `INPUT_IDENTITY_FREEZE`: after the run, candidate Git-blob identities must still be reconciled to an immutable canonical source commit / path before the frozen `DATA_IDENTITY.json` can be created.
