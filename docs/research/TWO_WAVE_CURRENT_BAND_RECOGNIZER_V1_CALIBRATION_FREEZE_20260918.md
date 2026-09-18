# Two-Wave current-band recognizer V1 — calibration freeze

Issue #420. Target oracle: frozen V2.1 primary taxonomy.

## Status

`CALIBRATION_FROZEN_PROGRESSION_GATE_PASSED`

This checkpoint freezes recognizer V1 parameters **before** the protected evaluation labels are opened.

## Frozen target

Final V2.1 primary-label SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

Split:

- calibration: 322
- protected evaluation: 78
- protected labels remained mode `000` throughout calibration
## Fixed gates

LOW_AMPLITUDE_VETO remains exactly:

`A_local_bps < 31.03573193149245`

FINER_SCALE_OUT_OF_BAND remains exactly the preregistered five-condition subband gate plus local alternation gate.

Calibration results for the fixed gates:

- LOW calibration rows: 34 / 34 recalled
- FINER calibration rows: 2 / 2 recalled
- LOW false positives: 0
- FINER false positives: 0

No LOW or FINER threshold was calibrated.

## Frozen direction weights

Coordinate order:

1. four-bar projection phase 0
2. four-bar projection phase 1
3. four-bar projection phase 2
4. four-bar projection phase 3
5. raw min-leg-4 pivot-chain coordinate

Frozen convex weights:

`[0.5371004573470922, 0.02422511769054332, 0.2549557883167388, 0.08538362512087591, 0.09833501152474969]`

They are nonnegative and sum to one.

Direction threshold remains frozen at `±0.20`.
## Calibration result

Five-state exact identity:

`0.922360248447205`

Macro recall:

`0.9379002192982456`

Per-state recall:

- CURRENT_UP: `0.9333333333333333`
- CURRENT_RANGE: `0.8421052631578947`
- CURRENT_DOWN: `0.9140625`
- LOW_AMPLITUDE_VETO: `1.0`
- FINER_SCALE_OUT_OF_BAND: `1.0`

Minimum state recall:

`0.8421052631578947`

All preregistered progression gates pass.

Calibration feature matrix SHA256:

`a33c325ccabc2cc51d330b4176f001f59909a5d95e3176edd5d04a1d5ab0c272`

Calibration receipt SHA256:

`50cd0bfc104e35486549d9f2b60e82e50da981696196e731f78232c69d01fa9a`
## Protected-evaluation rule

After this freeze is committed:

1. the 78 protected labels may be opened once;
2. evaluate with the exact frozen implementation, gates, weights and ±0.20 threshold;
3. report the full confusion matrix and per-state recall/precision;
4. do not retune V1 afterward, regardless of result.

If protected evaluation is unacceptable, V1 is rejected and a new recognizer version must be preregistered.

## Authority

No signal, trade, router, PnL-selection, paper/live or production authority.
