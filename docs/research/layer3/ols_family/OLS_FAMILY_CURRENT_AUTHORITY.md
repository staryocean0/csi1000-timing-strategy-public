# OLS Layer3 current research authority

Last updated: 2026-09-16

## Current state

The OLS family is **not production-authorized**. The active research program remains the MaxDD-first failure-regime program defined by `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`. **Phase C intervention authority remains closed.**

The only newly authorized continuation is the separately preregistered causal-identification study `ols-maxdd-sequence-hazard-v1` under `OLS_MAXDD_SEQUENCE_HAZARD_V1_PROTOCOL_20260916.md`.

## Closed prior sequence

- **D0 — drawdown diagnosis:** completed. Exit persistence is a material drawdown amplifier; large episodes often contain substantial fit-quality deterioration.
- **D1 — R² lead/lag:** completed and supported as a diagnostic. Two consecutive active-authority R² declines have useful early-warning information.
- **D2 — hard exit overlay:** completed and rejected. Authoritative status: `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.
- **Phase A — MaxDD failure atlas:** completed by verified run `34978764073-1`; authoritative status `MECHANISM_ATLAS_COMPLETED`.
- **Phase B — causal pre-segment re-entry identification:** completed by verified run `35040712447-1`; none of the eight frozen candidates passed the preregistered promotion gate; authoritative status `phase_c_authority=false`.

## What remains established

Phase A remains authoritative descriptive evidence that tail risk is concentrated in a small number of episodes, repeated participation/re-entry is associated with deeper drawdown episodes across all five frozen exit families, and fit-R²/path-efficiency collapse are severity markers, especially under frozen-midline persistence. These are episode-level mechanism findings, not a causal trading signal.

Phase B remains authoritative evidence that the tested **single-decision pre-segment snapshots** do not reliably identify which next segment will add further drawdown. Therefore none of those eight candidates may be converted into block-entry, cooldown, sizing, faster-exit, or risk-off rules under that experiment.

## New causal unit

The sequence-hazard study changes only the research unit, not the strategy. It asks whether a still-open underwater episode can be recognized as persistently dangerous from its **causal completed-segment path prefix**.

The primary checkpoint is one observation per recovered drawdown episode: the decision close before the first new segment that begins after two natural baseline segments have already completed within that same episode. Sequence length 2 is primary; length 3 is the only frozen sensitivity. Features, outcome, sufficiency rules and promotion gates were frozen before outcome reveal.

The study may measure cumulative loss/MAE burden, R²/PE collapse burden, damage acceleration, participation density and direction-change behavior across the completed prefix. It may not suppress trades or choose trading thresholds.

## Binding priority

1. Reduce maximum drawdown.
2. Reduce tail-drawdown severity and improve stability across periods.
3. Only after those risk objectives are achieved, recover gross return subject to the safer risk floor.

## Current authority

Authorized next study: **`ols-maxdd-sequence-hazard-v1`**.

Protocol: `OLS_MAXDD_SEQUENCE_HAZARD_V1_PROTOCOL_20260916.md`.

`phase_c_reopen_authority` is false before results and becomes true only if at least one frozen sequence candidate passes every preregistered cross-family, AUC, annual-stability, sequence-3 sensitivity and causal-availability condition. A pass would authorize only a separate preregistered intervention comparison.

No entry/exit/re-entry/sizing/routing/leverage/production change is authorized.