# OLS Layer3 current research authority

Last updated: 2026-09-15

## Current state

The OLS family is **not production-authorized**. The active research authority is the MaxDD-first failure-regime program defined by `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.

## Closed prior sequence

- **D0 — drawdown diagnosis:** completed. Exit persistence is a material drawdown amplifier; large episodes often contain substantial fit-quality deterioration.
- **D1 — R² lead/lag:** completed and supported as a diagnostic. Two consecutive active-authority R² declines have useful early-warning information.
- **D2 — hard exit overlay:** completed and rejected. The frozen mapping `first two-down warning -> flat next executable bar -> lockout until original segment end` reduced risk in some families but destroyed too much return and failed four of five preregistered gates. Authoritative status: `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.
- **Phase A — MaxDD failure atlas:** completed by verified run `34978764073-1`; authoritative status `MECHANISM_ATLAS_COMPLETED`.

D2 rejection closes that exact action mapping. It does not authorize rescue tuning of the same experiment, and it does not erase D1's diagnostic evidence.

## Phase A authoritative mechanism findings

Phase A established the following descriptive facts across the five frozen exit families:

1. Tail risk is highly concentrated: the deepest 20 episodes account for roughly 92%–97% of squared drawdown depth by family.
2. Repeated participation is a cross-family mechanism: segment/re-entry counts are materially higher in top-tail episodes and re-entry count is positively associated with drawdown depth across all five families.
3. Fit-R² and path-efficiency collapse are common severity markers; frozen-midline has the strongest confidence-collapse signatures and the largest MaxDD.
4. Simple three-consecutive-R²-decline counts are not a universal mechanism; they are concentrated primarily in persistent frozen-midline failures.
5. Authority-window switching is not a general top-tail driver in the atlas; the top-tail median switch count is zero in every family.
6. Cross-family overlap shows several long bad-state clusters that hit all five exit families, supporting a common failure-state program rather than isolated exit-family patching.

These findings are diagnostic. They do not themselves define a trading rule.

## Active question

The next question is:

> At the causal decision point before a new executable segment, can the dangerous combination of underwater repeated participation, recent confidence damage and apparent confidence recovery be identified before the next segment expands drawdown?

## Binding priority

1. Reduce maximum drawdown.
2. Reduce tail-drawdown severity and improve stability across periods.
3. Only after those risk objectives are achieved, recover gross return subject to the safer risk floor.

## Authorized next phase

**Phase B — `ols-maxdd-reentry-identification-v1`**

Protocol: `OLS_MAXDD_PHASE_B_REENTRY_IDENTIFICATION_PROTOCOL_20260915.md`.

Phase B is causal-identification research only. It may reconstruct frozen baseline segments and measure only information available at the decision close immediately before each executable segment. It may evaluate preregistered churn, prior-confidence-damage and false-recovery features against future drawdown extension of the naturally occurring baseline segment.

It may **not**:

- alter entry or exit logic;
- block or add trades;
- choose R²/PE/cooldown thresholds;
- optimize feature weights;
- choose a winner by total PnL;
- change sizing, routing or leverage;
- claim fresh OOS;
- grant production authority.

Phase C intervention authority exists only if at least one frozen Phase-B candidate passes the preregistered promotion gate. Any Phase C action experiment requires a new profile and protocol.