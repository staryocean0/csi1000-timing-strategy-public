# OLS Layer3 current research authority

Last updated: 2026-09-16

## Current state

The OLS family is **not production-authorized**. The active research program remains the MaxDD-first failure-regime program defined by `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.

The preregistered sequence-hazard study has now completed successfully. Its authoritative verified run is `35043295079-1`, with `phase_c_reopen_authority=true`.

## Closed prior sequence

- **D0 — drawdown diagnosis:** completed. Exit persistence is a material drawdown amplifier; large episodes often contain substantial fit-quality deterioration.
- **D1 — R² lead/lag:** completed and supported as a diagnostic.
- **D2 — hard exit overlay:** completed and rejected. Authoritative status: `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.
- **Phase A — MaxDD failure atlas:** completed by verified run `34978764073-1`; authoritative status `MECHANISM_ATLAS_COMPLETED`.
- **Phase B — causal pre-segment re-entry identification:** completed by verified run `35040712447-1`; none of the eight frozen single-entry candidates passed; `phase_c_authority=false` for that experiment.
- **Sequence-hazard v1 — state-path causal identification:** completed by verified run `35043295079-1`; two frozen candidates passed the preregistered promotion gate; `phase_c_reopen_authority=true`.

## What the sequence-hazard result establishes

The valid causal unit is not a generic single re-entry snapshot. The successful study instead uses one state-path checkpoint per recovered drawdown episode after two natural baseline segments have already completed while equity remains underwater.

Two preregistered sequence candidates are eligible for a separately preregistered Phase C intervention comparison:

1. `seq_pe_collapse_burden` — accumulated path-efficiency collapse across the completed two-segment prefix.
2. `seq_direction_flip` — direction reversal across the completed two-segment prefix.

`seq_pe_collapse_burden` passed with positive primary rho in all five exit families, rho >= 0.25 in three, median family AUC about 0.667, positive annual rho in 5 of 6 sufficient family-year cells, and positive sequence-3 sensitivity rho in all five families.

`seq_direction_flip` passed with positive primary rho in all five exit families, rho >= 0.25 in four, median family AUC about 0.622, positive annual rho in 5 of 6 sufficient family-year cells, and positive sequence-3 sensitivity rho in four of five families.

This is a research-sample identification result, not fresh OOS and not a trading rule. Annual sufficiency remains sparse.

## Binding priority

1. Reduce maximum drawdown.
2. Reduce tail-drawdown severity and improve stability across periods.
3. Only after those risk objectives are achieved, recover gross return subject to the safer risk floor.

## Current authority

**Phase C intervention-research authority is reopened, but only for a new separately preregistered comparison built from the two eligible sequence-hazard candidates.**

The next study may compare a bounded ladder of risk responses and must freeze all trigger construction, action semantics, MaxDD/tail gates, return-retention floors, and robustness checks before observing intervention outcomes.

The sequence-hazard result itself does not authorize live block-entry, cooldown, sizing, faster exit, full risk-off, routing, leverage, deployment, or production behavior.

No production or live-trading authority is granted.