# OLS Layer3 current research authority

Last updated: 2026-09-15

## Current state

The OLS family is **not production-authorized**. The active research authority is the MaxDD-first failure-regime program defined by `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.

## Closed prior sequence

- **D0 — drawdown diagnosis:** completed. Exit persistence is a material drawdown amplifier; large episodes often contain substantial fit-quality deterioration.
- **D1 — R² lead/lag:** completed and supported as a diagnostic. Two consecutive active-authority R² declines have useful early-warning information.
- **D2 — hard exit overlay:** completed and rejected. The frozen mapping `first two-down warning -> flat next executable bar -> lockout until original segment end` reduced risk in some families but destroyed too much return and failed four of five preregistered gates. Authoritative status: `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.

D2 rejection closes that exact action mapping. It does not authorize rescue tuning of the same experiment, and it does not erase D1's diagnostic evidence.

## Active question

The next question is no longer "which R² exit threshold wins?" It is:

> Which causally observable failure regimes produce the OLS tool's largest drawdowns, why do they produce those losses, and what later intervention can reduce those losses with the smallest necessary sacrifice of profitable trend participation?

## Binding priority

1. Reduce maximum drawdown.
2. Reduce tail-drawdown severity and improve stability across periods.
3. Only after those risk objectives are achieved, recover gross return subject to the safer risk floor.

## Authorized next phase

**Phase A — `ols-maxdd-failure-atlas-v1`**

This phase is descriptive/mechanistic only. It may rebuild the frozen five exit families and measure drawdown episodes, model-confidence paths, authority switching, exit density, entries/re-entries, position flips and related causal state variables. It may contrast top-tail drawdowns with ordinary drawdowns.

It may **not**:

- alter entry or exit logic;
- select R²/PE/cooldown thresholds;
- choose a winner by PnL;
- change sizing, routing or leverage;
- claim fresh OOS;
- grant D2b or production authority.

Any later Phase B/C intervention requires a separate preregistration after Phase A evidence is reviewed.
