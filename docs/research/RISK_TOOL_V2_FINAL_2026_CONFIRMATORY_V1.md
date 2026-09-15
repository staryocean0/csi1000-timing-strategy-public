# Risk Tool 2.0 — final 2026 confirmatory protocol v1

Date: 2026-09-15
Status: `FROZEN_BEFORE_RISK_TOOL_2026_SEMANTIC_READ`

## Finite endpoint

This is the final scientific stage for the current Risk Tool 2.0 line. It is not another development loop.

After this one 2026 confirmatory evaluation, each 15m/30m horizon is adjudicated once as validated, not validated, or out of support. No model, calibration, tail limit, support gate, carrier, date range, horizon, or symbol may be changed to rescue the result. There is no v3/v4 successor inside this task.

A full pass validates a Layer2 research component only. A partial pass validates only the passing horizon for Layer3 research consumption. No pass closes the current Risk Tool 2.0 candidate as not validated. Nothing here grants PnL, routing, sizing, or production authority.

## Evidence level

The 2026 market material has existed elsewhere in the project, so this run is **not claimed to be globally fresh OOS**. It is a preregistered one-shot confirmatory evaluation for this frozen Risk Tool hypothesis. `fresh_oos_claim=false`.

## Frozen model candidate

Parent score identity remains the Phase-1 `MODEL_FREEZE.json`:

- SHA256 `b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551`
- development years 2021-2023
- ridge lambda `0.01`
- no refit

Base Phase-1b calibration remains:

- SHA256 `74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909`
- fixed audit Platt parameters
- no refit

Final Development candidate is frozen from consumed-data run `34920654435-1`:

- 15m: keep frozen raw B/C ordering scores; keep B Platt calibration unchanged; apply only to calibrated C the selected strictly monotone tail transform `tail_L_4`.
- 15m tail anchor event rate: `0.2312353159391616`.
- 15m tail limit: `L=4.0`.
- transform: with `a=logit(anchor)` and `z=logit(p_C_cal)`, `z2 = a + L*tanh((z-a)/L)`, then `p2=sigmoid(z2)`.
- 30m: unchanged frozen Phase-1b audit Platt calibration for B and C.
- 2024-2025 repeat-audit years did not choose the tail candidate.
- no new ordering training.

The consumed-data hierarchical-v1 result remains attached to its original profile as `TS-I` because weekly support was an ex-ante hard gate. The weekly support diagnostic is not used to weaken or rewrite that historical result.

## User-provided 2026 carrier

The only authorized 2026 carrier is the already-sealed cross-index 1m pack in `staryocean0/factorlab-star50-filter-lab` under `data/cross_index_risk_gate_2026_v1/1m/`.

The source manifest records 154 trading days from 2026-01-05 through 2026-08-21, `new_ohlc_created=false`, `interpolation=false`, and the common Unified DataHub parent export `factorlab_unified_index_kline_v3_20260824`.

Immutable file identities:

- `000688.SH`: Git blob `4626fb307bbcae1c417ddcd69ac694cf322c8bbc`, 584376 bytes, SHA256 `b7e7e9a9e85b738d661583dcd3d7dab158562fddac4355362cc37597db21eca4`.
- `000852.SH`: Git blob `8de5cd3caab99dbacae229a2c87f15c4ff2f8558`, 707905 bytes, SHA256 `60b2054d2055bef8010a9948a0589bc1c4b0bb18dd6f373a9366f97e689fdf87`.

No external or alternate market source is allowed.

## Frozen 1m -> 5m construction and guard

The user previously explicitly authorized constructing 5m bars from this repository's 1m index bars, because the existing project 5m bars are themselves constructed from the 1m source. Before any 2026 score is computed, the construction must pass a 2023 equivalence guard on both symbols.

For each symbol and trading day independently:

1. sort by displayed Shanghai session time;
2. require exactly 120 morning and 120 afternoon 1m rows;
3. partition each half-session into 24 consecutive non-overlapping groups of five;
4. synthesized 5m close is the fifth 1m close in each group;
5. carry only the fifth source timestamp as the ordering timestamp;
6. no interpolation, forward fill, or future-row use;
7. require exactly 48 synthesized 5m rows per complete day.

Guard identities:

- 000688 2023 1m: blob `6dc7de6de7fe04233566b2a1743de66b054df18b`, 1156684 bytes.
- 000688 2023 native 5m: blob `02c3a9474dff4e5203cec12ca7a24a3b2be8994b`, 309025 bytes.
- 000852 2023 1m: blob `a915cc9a0e9259e2660558c07ffbe1d6c37c0e8f`, 1507783 bytes.
- 000852 2023 native 5m: blob `0b17d76b150bfd15d45158f100748898e72089b1`, 342750 bytes.

The guard requires identical trading-day support, 48 rows/day on both representations, timestamp alignment after chronological construction, and maximum absolute close difference `<=1e-9`. Failure stops before any 2026 parquet is deserialized for scoring.

## Warm-up

Only frozen native 2025 5m shards are used for warm-up:

- 000688: blob `32d6d1754f965dd6298c885e30b244b877d694ed`, 320754 bytes, SHA256 `bb0b3a5747f11bf5e8908ac169185b582213fcc83a74567e683a56410ceb8511`.
- 000852: blob `85159b9fa1b2b6854b1a0f04faa9f963e9d04c13`, 353882 bytes, SHA256 `5fbecf49d76cd2560e7db5af280b60c012a440a6e69ba6b8306acbbbd4e49333`.

2025 rows are never scored in the confirmatory sample.

## Frozen cohort and horizons

- symbols exactly `000688.SH`, `000852.SH`;
- score only 2026 rows through the sealed carrier end date 2026-08-21;
- horizons exactly 15m and 30m;
- state construction, episode construction, recent-shock age buckets, Severity variables, and no-lunch-crossing labels remain identical to frozen Phase-1 semantics;
- no full-calendar-year claim.

## Support gate

Each horizon is judged independently. Required before scientific acceptance:

- pooled eligible rows >= 1000;
- each symbol eligible rows >= 150;
- pooled positives >= 100;
- pooled negatives >= 100;
- both symbols contain both target classes.

Failure gives `OUT_OF_SUPPORTED_CONFIRMATORY_2026`; thresholds are not loosened.

## Primary metrics and uncertainty

For each supported horizon:

1. raw ordering gain = `AUROC(C_raw) - AUROC(B_raw)`;
2. calibrated Brier gain = `Brier(B_cal) - Brier(C_cal)`;
3. calibrated LogLoss gain = `LogLoss(B_cal) - LogLoss(C_cal)`.

Positive means challenger C is better.

Uncertainty is paired trading-day cluster bootstrap with both symbols kept together within sampled days:

- repetitions: 5000;
- seed: 20260914;
- family size: 6 primary tests (2 horizons x 3 gains);
- one-sided family alpha: 0.05;
- Bonferroni lower quantile: `0.05/6 = 0.008333333333333333`.

## Per-horizon acceptance

A supported horizon is `CONFIRMATORY_2026_VALIDATED` only if all are true:

- pooled raw AUROC gain > 0;
- family-adjusted bootstrap lower bound for raw AUROC gain > 0;
- raw AUROC gain is nonnegative for each symbol;
- pooled calibrated Brier gain > 0;
- family-adjusted bootstrap lower bound for calibrated Brier gain > 0;
- pooled calibrated LogLoss gain > 0;
- family-adjusted bootstrap lower bound for calibrated LogLoss gain > 0;
- calibrated Brier gain is nonnegative for each symbol;
- calibrated LogLoss gain is nonnegative for each symbol.

One horizon cannot rescue the other.

## Final task adjudication

- both horizons validated -> `LAYER2_CONFIRMATORY_FULL_VALIDATION`;
- exactly one validated -> `LAYER2_CONFIRMATORY_PARTIAL_VALIDATION`, and only that horizon may be handed to Layer3 as a research input;
- supported horizons but none validated -> `RISK_TOOL_V2_CLOSED_NOT_VALIDATED`;
- no horizon has adequate support -> `RISK_TOOL_V2_CLOSED_INSUFFICIENT_CONFIRMATORY_SUPPORT`.

After this adjudication the current Risk Tool 2.0 research task is closed. There is no automatic next calibration family, threshold change, carrier replacement, date trimming, symbol deletion, new horizon, new scale, or second 2026 attempt.

`production_authority=false`.
