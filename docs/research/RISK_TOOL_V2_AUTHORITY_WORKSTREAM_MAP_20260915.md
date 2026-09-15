# Risk Tool V2 — authority and workstream map — 2026-09-15

> Coordination/read-only map. This document does **not** replace PRIVATE `CLOUD_CURRENT.json`, pinned run branches, preregistrations, or any scientific authority artifact. It exists to stop parallel agents from creating competing Risk Tool lines. Coordination anchor: public issue #173.

## Unified ownership boundary

All `risk-v2-*` research, diagnostics, contracts, and bounded runtime integration belong to one governed Risk Tool V2 program. Existing authority/results are immutable; future work must extend them through a separately reviewed preregistration/profile.

Two previously parallel lanes answer different questions and must not be post-hoc merged into one verdict:

1. **Phase-1 / Phase-1b / fresh-OOS lane** — asks whether the frozen risk representation generalizes to newly exposed 2026 data.
2. **Temporal-stability / Reliability / consumer lane** — asks which historical 2015–2025 outputs are stable enough to expose to downstream research consumers, and under what permissions.

## Current immutable authority map

| Surface | Authority run / location | Current reading | Boundary |
|---|---|---|---|
| 2026 Phase-1b fresh-OOS | `34956326542-1` / `research/public-runs/34956326542-1-fresh-oos-summary.json` | `INSUFFICIENT_2026_SUPPORT` | Support gate stopped acceptance; no model-support or model-failure claim |
| Historical temporal v3 | `34930354449-1` / `ACCEPTANCE_RESULT_V3.json` | 30m `TS-A_STABLE_PROBABILITY_COMPONENT`, `COMPLETE`; 15m `TS-B_STABLE_RANKING_CALIBRATION_GUARDED`, `IN_PROGRESS` | 15m bottleneck remains `weekly.calibration` |
| 15m continuous Reliability | `34942554638-1` / `RELIABILITY_RESULT.json` | supported; q33=`0.5170330932673238`, q67=`0.7096666848299501` | Reliability changes interpretation permissions only |
| Probability + Reliability output contract | `34945466654-1` / `OUTPUT_CONTRACT_RESULT.json` | `DUAL_OUTPUT_CONTRACT_SUPPORTED` | Does not promote 15m to COMPLETE |
| Layer2→Layer3 consumer contract | `34954265620-1` / `CONSUMER_CONTRACT_RESULT.json` | `CONSUMER_CONTRACT_SUPPORTED`; 35 fixed cases passed | No hard threshold/routing/sizing/PnL/production authority |
| PRIVATE runtime consumer adapter | PRIVATE `main`: `runtime/src/factor_lab/market_state/risk_probability_reliability_consumer_v1.py` | installed, fail-closed | Research consumer interface only |

### Fresh-OOS support snapshot

The frozen 2026 result is not a failed model test; it is an insufficient-support result.

- 15m: 754 usable rows; `000688.SH=0`, `000852.SH=754`; 184 positive, 570 negative; 70 trading-day clusters.
- 30m: 690 usable rows; `000688.SH=0`, `000852.SH=690`; 319 positive, 371 negative; 67 trading-day clusters.
- Frozen support gates require total rows >=1200, each of two symbols >=500, positives >=100, negatives >=100, and trading-day clusters >=100.

The zero for `000688.SH` is a property of the **final frozen support cohort**. It must not be reinterpreted as proof that the physical carrier lacks `000688.SH`.

## Historical lane semantics

The 2015–2025 temporal hard-gate lane intentionally fixes the primary longitudinal carrier to `000852.SH`, because canonical 2015–2019 history exists only for that symbol. `000688.SH` is outside that historical hard-gate claim. Therefore:

- historical 30m `COMPLETE` is not a 2026 fresh-OOS pass;
- 2026 `INSUFFICIENT_2026_SUPPORT` does not silently revoke historical 30m authority;
- neither lane may be used to rescue or invalidate the other after results are known.

## Current active bottlenecks

1. **2026 cohort attrition** — locate the first frozen pipeline checkpoint at which `000688.SH` becomes zero.
2. **15m historical weekly calibration** — remains guarded; Reliability is a permission overlay, not a calibration refit.
3. **Serving semantics** — preserve the existing fail-closed consumer contract while documenting how historical authority and separate 2026 support status are surfaced together.

## Non-negotiable prohibitions

- no post-result refit, retuning, threshold rescue, cutoff extension, or substitute data;
- no rewriting historical authority because of the 2026 insufficient-support outcome;
- no claiming 2026 support from historical temporal results;
- no hard probability thresholding, strategy routing, position sizing, PnL authority, or production authority without a new separately reviewed contract;
- no direct Chat writes to PRIVATE; all private results/runtime changes use bounded reviewed PUBLIC broker/sync mechanisms.

## Next governed action

Run `risk-v2-phase1b-fresh-oos-attrition-v1`, a diagnostic-only aggregate trace that reuses the exact accepted carrier, cutoff, state logic, cohort logic, and support gates from the frozen parent fresh-OOS run. It exports only aggregate counts and the first zero-count checkpoint per symbol, changes no scientific verdict, and executes no model or calibration.
