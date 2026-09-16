# Risk Tool V2 — authority and workstream map — 2026-09-15

> Coordination/read-only map. This document does **not** replace PRIVATE `CLOUD_CURRENT.json`, pinned run branches, preregistrations, or scientific authority artifacts. Coordination anchor: public issue #173.

## Unified ownership boundary

All `risk-v2-*` authority, diagnostics, consumer contracts, and the governed Risk Tool V3 native-scale successor line belong to one Risk Tool program. Existing V2 results remain immutable.

The successor program now follows a **top-down native-scale attribution order: 60m → 15m → 5m**.

This changes research priority, not past results.

## Critical scale rule

- Native-60m means the primitive observations are 60-minute K-lines.
- Native-15m means the primitive observations are 15-minute K-lines.
- Native-5m means the primitive observations are 5-minute K-lines.
- Existing V2 “15m / 30m” authority refers to forecast horizons of the 5m-base tool and must never be relabeled as Native-15m / Native-30m tools.

## Current immutable V2 authority

| Surface | Authority | Current reading | Boundary |
|---|---|---|---|
| 2026 Phase-1b fresh-OOS | run `34956326542-1` | `INSUFFICIENT_2026_SUPPORT` | Support gate stopped acceptance; not a model-failure verdict |
| Fresh-OOS attrition | run `34965394157-1` | `000688.SH` first zero at `physical_projected` | Diagnostic-only; parent verdict unchanged |
| Future carrier binding | run `34970778993-1` | `SOURCE_FAMILY_BINDING_VALID` | Future source-family identity only |
| Future-OOS V2 prereg | merge `745b7a79c461a543b5e3ffd7884b7d86fc09f1f8` | 2026-09-16 through 2027-03-31; execution closed pending full future snapshot | No early reveal |
| Historical temporal v3 | run `34930354449-1` | 30m `TS-A_STABLE_PROBABILITY_COMPONENT`, COMPLETE; 15m `TS-B_STABLE_RANKING_CALIBRATION_GUARDED`, IN_PROGRESS | Both are forecast horizons of native-5m V2 |
| 15m Reliability | run `34942554638-1` | supported | Interpretation/permission overlay only |
| Probability + Reliability output | run `34945466654-1` | `DUAL_OUTPUT_CONTRACT_SUPPORTED` | No hard threshold authority |
| Layer2→Layer3 consumer contract | run `34954265620-1` | `CONSUMER_CONTRACT_SUPPORTED` | No routing/sizing/PnL/production authority |

## Preserved Native-15m V3 evidence

The Native-15m work performed before the top-down amendment remains authoritative for exactly what it tested:

- Phase A carrier/semantic audit: valid Native-15m carrier foundation.
- Phase B 2021–2023 descriptive risk map: complete.
- Phase C1 576-candidate state-machine map: `NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT`, `passing_count=0`, no C2 authority.
- C1 gate-attribution diagnostic: complete; it showed that current severity separation and next-bar persistence gates were broadly satisfied, while fixed pooled/annual tail-event capture—especially pooled q95 capture—was the dominant incompatibility.

These findings must not be rewritten as a successful Native-15m state machine, and the frozen C1 gates must not be relaxed post-result under the same test identity.

The program is pausing further Native-15m parameter search until large-scale risk hierarchy is characterized from 60m downward.

## 2026-09-16 direction amendment: top-down risk attribution

### Why the direction changed

K-lines are lossy compression. A larger bar can hide a large amount of smaller-scale movement. A 60m candle can have a small body while containing violent intrabar oscillation.

Therefore multi-scale Risk Tool research is not defined as “look at the same risk event from multiple resolutions.” It is defined as:

> **Find the class of risk that survives aggregation at a large native scale, then open that bar and explain how smaller native bars generated it.**

### Hierarchy hypothesis to test

- A genuine large-scale risk regime should normally leave stress structure in its constituent smaller bars.
- A small-scale shock may die locally and fail to create a large-scale regime.
- Large→small transmission is therefore expected to be stronger than small→large transmission, but this remains a hypothesis until measured.

## Active successor program: Native-60m first

### Source contract

Current PRIVATE data inventory lists:

- `data/index/1m_official.parquet`, 2015-01-05 through 2026-08-21;
- provider-supplied `5m_offset_0` and `15m_offset_5` views;
- no provider-supplied 60m view.

Therefore the active Native-60m line must freeze a deterministic, session-aware transformation from `1m_official` into canonical 60m bars. It must not define 60m authority by casually aggregating 5m/15m bars.

### Information that must survive 60m construction

Because candle body alone can hide intrabar risk, the canonical research representation should preserve:

- OHLC;
- absolute 60m body;
- high-low range;
- close-to-close return where causal;
- intrabar 1m realized volatility / path energy within the exact 60m interval.

### Intended A-share session geometry, subject to semantic audit

The desired four wall-clock buckets are:

- 09:30–10:30;
- 10:30–11:30;
- 13:00–14:00;
- 14:00–15:00.

No bucket may bridge the lunch break. Exact endpoint inclusion and timestamp labels must be frozen only after auditing the official 1m source semantics.

## Active research sequence

1. **Native-60m Phase 60-A:** audit `1m_official`, freeze deterministic 1m→60m membership and verify four complete bars per normal trading day.
2. **Native-60m Phase 60-B:** descriptive continuity map using body, range, close-to-close magnitude, and intrabar 1m realized volatility/path energy.
3. Test lag persistence, conditional next-bar risk, episode/run lengths, time-of-day slot effects, and year stability without optimizing thresholds.
4. Only if meaningful 60m continuity is established: preregister candidate Native-60m risk-state definitions.
5. **60m → 15m decomposition:** compare constituent 15m structure inside high-risk vs low-risk 60m bars.
6. **15m → 5m decomposition:** explain finer stress structure conditional on the higher-scale state.
7. Revisit Native-15m state design only after the top-down hierarchy is understood; prior C1 remains immutable.

## Current active bottlenecks

1. **Native-60m canonical construction / semantic audit** from official 1m — active next task.
2. **Native-60m volatility-continuity map** — first scientific question after construction is validated.
3. **Native-15m state-machine C1** — closed as insufficient under its frozen gates; no C2 authority.
4. **V2 15m weekly calibration** — still guarded; separate from native-scale V3.
5. **Future-OOS V2** — intentionally closed until its full preregistered future window is available.

## Non-negotiable prohibitions

- no confusing native K-line scale with forecast horizon;
- no copying 5m thresholds/windows into 60m as authority;
- no rescuing Native-15m C1 by post-result gate or grid changes;
- no defining 60m risk from candle body alone while discarding the available official-1m intrabar path;
- no crossing the A-share lunch break inside a canonical 60m bar;
- no 2026 threshold training unless separately preregistered;
- no strategy routing, position sizing, PnL, or production authority from this research line;
- no direct Chat writes to PRIVATE.

## Next governed action

Start **Risk Tool V3 Native-60m Phase 60-A**: pin the official 1m carrier, independently audit its timestamp/session/OHLC semantics, and freeze the deterministic four-bars-per-day 1m→60m construction before any volatility threshold or state-machine search.

After Phase 60-A passes, run a descriptive Native-60m continuity study. The primary question is whether large-scale risk intensity is temporally persistent enough to act as a Layer2 regime context, not whether it immediately improves trading.