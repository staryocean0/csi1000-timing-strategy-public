# Risk Tool V2 — authority and workstream map — 2026-09-15

> Coordination/read-only map. This document does **not** replace PRIVATE `CLOUD_CURRENT.json`, pinned run branches, preregistrations, or any scientific authority artifact. It exists to stop parallel agents from creating competing Risk Tool lines. Coordination anchor: public issue #173.

## Unified ownership boundary

All `risk-v2-*` research, diagnostics, contracts, bounded runtime integration, and the governed native-scale successor program belong to one Risk Tool program. Existing V2 authority/results are immutable; future work must extend them through separately reviewed research contracts.

Two previously parallel V2 lanes answer different questions and must not be post-hoc merged into one verdict:

1. **Phase-1 / Phase-1b / fresh-OOS lane** — asks whether the frozen 5m-base risk representation generalizes to newly exposed data.
2. **Temporal-stability / Reliability / consumer lane** — asks which historical 5m-base outputs are stable enough to expose to downstream research consumers, and under what permissions.

A third, successor research direction is now explicitly authorized as the next development lane:

3. **Native K-line multi-scale lane (Risk Tool V3 research)** — rebuild the same risk-measurement philosophy natively on 15m and 60m K-lines, then study 5m × 15m × 60m cross-scale escalation and recovery. See `docs/research/RISK_TOOL_V3_NATIVE_KLINE_MULTISCALE_ROADMAP_20260915.md`.

## Critical scale-semantics rule

For the successor lane, **15m and 60m mean the base K-line interval itself**.

- Native-15m means returns, volatility, shocks, state transitions, state ages and labels are generated from a 15-minute K-line sequence.
- Native-60m means the same objects are generated from a 60-minute K-line sequence.
- They do **not** mean the current 5m tool predicting 15 or 60 minutes ahead.
- Existing V2 15m/30m results are forecast horizons of the 5m-base tool and must never be relabeled as native 15m/30m Risk Tools.

This distinction is non-negotiable for all future agents and implementations.

## Current immutable V2 authority map

| Surface | Authority run / location | Current reading | Boundary |
|---|---|---|---|
| 2026 Phase-1b fresh-OOS | `34956326542-1` / `research/public-runs/34956326542-1-fresh-oos-summary.json` | `INSUFFICIENT_2026_SUPPORT` | Support gate stopped acceptance; no model-support or model-failure claim |
| Fresh-OOS cohort attrition diagnostic | `34965394157-1` / `research/public-runs/34965394157-1-attrition.json` | `000688.SH` first zero at `physical_projected`; accepted physical carrier is 135,682 rows of `000852.SH` only | Diagnostic-only; parent fresh-OOS verdict unchanged |
| Future source-family binding audit | `34970778993-1` / private mirrored `BINDING_AUDIT.json` | `SOURCE_FAMILY_BINDING_VALID` | Correct source-family / symbol-binding authority for future work; not a scientific model verdict |
| Future-OOS V2 prereg | public merge `745b7a79c461a543b5e3ffd7884b7d86fc09f1f8` | window frozen from `2026-09-16` through `2027-03-31`; execution intentionally closed pending complete new snapshot | Does not consume future observations early |
| Historical temporal v3 | `34930354449-1` / `ACCEPTANCE_RESULT_V3.json` | 30m `TS-A_STABLE_PROBABILITY_COMPONENT`, `COMPLETE`; 15m `TS-B_STABLE_RANKING_CALIBRATION_GUARDED`, `IN_PROGRESS` | These 15m/30m labels are forecast horizons of the native-5m V2 tool, not K-line base scales |
| 15m continuous Reliability | `34942554638-1` / `RELIABILITY_RESULT.json` | supported; q33=`0.5170330932673238`, q67=`0.7096666848299501` | Reliability changes interpretation permissions only |
| Probability + Reliability output contract | `34945466654-1` / `OUTPUT_CONTRACT_RESULT.json` | `DUAL_OUTPUT_CONTRACT_SUPPORTED` | Does not promote the 15m forecast horizon to COMPLETE |
| Layer2→Layer3 consumer contract | `34954265620-1` / `CONSUMER_CONTRACT_RESULT.json` | `CONSUMER_CONTRACT_SUPPORTED`; 35 fixed cases passed | No hard threshold/routing/sizing/PnL/production authority |
| PRIVATE runtime consumer adapter | PRIVATE `main`: `runtime/src/factor_lab/market_state/risk_probability_reliability_consumer_v1.py` | installed, fail-closed | Research consumer interface only |

### Fresh-OOS support snapshot and resolved attrition location

The frozen 2026 result is not a failed model test; it is an insufficient-support result.

- 15m forecast horizon: 754 usable rows; `000688.SH=0`, `000852.SH=754`; 184 positive, 570 negative; 70 trading-day clusters.
- 30m forecast horizon: 690 usable rows; `000688.SH=0`, `000852.SH=690`; 319 positive, 371 negative; 67 trading-day clusters.
- Frozen support gates require total rows >=1200, each of two symbols >=500, positives >=100, negatives >=100, and trading-day clusters >=100.

The follow-up diagnostic `risk-v2-phase1b-fresh-oos-attrition-v1` independently reproduced those support snapshots and traced aggregate counts through the unchanged frozen pipeline. It found `000688.SH=0` already at `physical_projected`, before temporal filtering, normalization, state construction, episode construction, fresh cohort construction, or horizon labeling.

The subsequent future carrier-binding audit repaired the future input-binding contract without rewriting the revealed parent test. The original fresh-OOS result remains immutable.

## Historical lane semantics

The 2015–2025 temporal hard-gate lane intentionally fixes the primary longitudinal carrier to `000852.SH`, because canonical 2015–2019 history exists only for that symbol. `000688.SH` is outside that historical hard-gate claim. Therefore:

- historical 30m `COMPLETE` is not a 2026 fresh-OOS pass;
- 2026 `INSUFFICIENT_2026_SUPPORT` does not silently revoke historical 30m authority;
- neither lane may be used to rescue or invalidate the other after results are known.

## Successor research direction: native multi-scale Risk Tool

The next active development direction is **not** to extend the current 5m tool to longer forecast horizons. It is to construct new, native K-line-base Risk Tools.

### Phase A — Native 15m

- use a true 15m K-line sequence as the primitive observation stream;
- prefer the existing DataHub-provided `15m_offset_5` view after a dedicated carrier/semantic audit;
- recompute returns, realized volatility, background volatility, shock intensity, state transitions and persistence on 15m bars;
- re-research all state-machine windows and thresholds from 15m data;
- use the 5m V2 methodology as a process template only, not as a parameter template;
- independently perform calibration, temporal stability, Reliability and OOS governance.

### Phase B — Native 60m

- first freeze a canonical 60m K-line carrier and session-boundary contract;
- if an official/provider 60m view is unavailable, define a deterministic session-aware transformation from official 1m data before model research;
- compute the entire risk state machine on 60m bars;
- independently research thresholds, windows, persistence, calibration and stability;
- do not mechanically scale 5m or 15m parameters.

### Phase C — Cross-scale stack

After both native tools earn their own scientific authority, study the joint state vector:

`[Risk_5m, Risk_15m, Risk_60m]`

Primary targets are escalation, persistence, recovery ordering, scale disagreement and whether cross-scale state provides more stable Layer2 context than any single scale.

This cross-scale layer remains measurement/state infrastructure and grants no trading authority by itself.

## Current active bottlenecks

1. **Native-15m carrier / semantic audit** — first executable task of the V3 lane.
2. **Native-15m descriptive risk map** — quantify event frequency, severity, persistence and recovery before freezing thresholds.
3. **Native-60m carrier definition** — confirm provider view or preregister deterministic 1m→60m construction with explicit lunch/session semantics.
4. **15m historical weekly calibration in V2** — remains guarded; Reliability is a permission overlay, not a calibration refit.
5. **Future-OOS V2** — remains intentionally closed until its preregistered future window has complete immutable data.

## Non-negotiable prohibitions

- no confusing K-line base interval with prediction horizon;
- no directly copying `RV_WINDOW=12`, `BG_WINDOW=48`, `SHOCK_SIGMA=3.0`, `HIGHVOL_RATIO=1.50`, or `RECOVERY_NORMAL_RATIO=1.10` into native 15m/60m as authoritative parameters;
- no post-result refit, retuning, threshold rescue, cutoff extension, or substitute data inside frozen V2 contracts;
- no rewriting V2 authority based on V3 experiments;
- no claiming native-15m/native-60m support from existing 5m-base horizon results;
- no hard probability thresholding, strategy routing, position sizing, PnL authority, or production authority without a new separately reviewed contract;
- no direct Chat writes to PRIVATE; all private results/runtime changes use bounded reviewed PUBLIC broker/sync mechanisms.

## Next governed action

Start **Risk Tool V3 Phase A: Native-15m** with a carrier / timestamp / session / symbol semantic audit of the existing `15m_offset_5` source. After the carrier is frozen, produce a descriptive native-15m risk map before searching or freezing state thresholds.

Native-60m follows only after its K-line carrier semantics are frozen. Cross-scale 5m × 15m × 60m work begins only after both native-scale tools have independent validated state processes.
