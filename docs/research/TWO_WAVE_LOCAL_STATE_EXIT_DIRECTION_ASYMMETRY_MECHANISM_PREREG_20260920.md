# Two-Wave Local State-Exit Direction Asymmetry Mechanism Audit — Preregistration

Date: 2026-09-20  
Issue: #647  
Status: **FROZEN BEFORE NEW OUTCOME ANALYSIS**

## 1. Why this study exists

The strategy-evolution authority now leaves one local structural fact unresolved.

Issue #624 showed that the target frequency's own frozen compression score contains real state-survival information, but the relationship was sharply asymmetric:

- CURRENT_DOWN: B5−B1 ≈ +17.16pp, bootstrap CI fully positive;
- CURRENT_UP: B5−B1 ≈ +3.96pp, CI crossing zero.

Issue #635 then tested the first permitted non-recursive current-context increment and rejected P128 as stable conditional incremental information.

Therefore this study does **not** escalate to P256/C2/C3 and does **not** revive future(C1)→future(C2). It returns to the evidence-retained local baseline and asks a smaller mechanistic question:

> Is the UP/DOWN asymmetry already present in the four frozen local compression components, or is it mainly an age/base-rate composition effect?

This is a mechanism audit on already-exposed development evidence, not a confirmatory rescue of #624.

## 2. Immutable evidence identity

Only the accepted #624 canonical scored ledger may be consumed:

- governed identity: `35488698309-1`;
- public source SHA: `828a64c763ba1e4f08b126a3766e54bb73a8e4d`;
- file: `ISSUE624_SCORED_LEDGER.csv`;
- SHA256: `c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f`;
- exact-result SHA256: `0760393f9a27b4a7db2ad65a931e449c68ca71c2aeba7a657867d9929743519b`;
- rows: 29,713;
- years: 2018 / 2019 / 2020.

No new years are fresh OOS here.

## 3. Frozen target and local inputs

Target remains exactly #624 Amendment-A `structural_exit_next8`.

States:
- `CURRENT_UP`
- `CURRENT_DOWN`

Frozen age bins:
- A1 1–4
- A2 5–8
- A3 9–16
- A4 17–32
- A5 33+

Frozen local components only:
- `abs_ret_8` → `risk_abs_ret_8`
- `range_8` → `risk_range_8`
- `rv_8` → `risk_rv_8`
- `efficiency_8` → `risk_efficiency_8`

The `risk_*` columns are the already-defined #624 prior-year reverse-percentiles. Higher values mean more compression under the frozen recipe.

The existing equal-weight `compression_score` is retained only as a reference decomposition.

## 4. Fixed analysis

For each state and each of the four frozen `risk_*` components:

1. assign fixed percentile quintiles `Q1=[0,.2]`, `Q2=(.2,.4]`, `Q3=(.4,.6]`, `Q4=(.6,.8]`, `Q5=(.8,1]`; values outside `[0,1]` fail and there is no outcome-derived threshold;
2. report event rate in Q1…Q5 and Q5−Q1;
3. repeat Q5−Q1 within each frozen age bin;
4. compute state/component age-standardized Q5−Q1 using that state/component Q1+Q5 support shares;
5. compute one common pooled-age weight vector from CURRENT_UP+CURRENT_DOWN Q1+Q5 support for that component and apply the same weights to both states;
6. report 2018/2019/2020 signs;
7. report all eight `known_index mod 8` cohort signs;
8. use 20-trading-day block bootstrap, 5000 repetitions, seed `20260920`;
9. define the component interaction as common-age-standardized `DOWN(Q5−Q1) − UP(Q5−Q1)` and bootstrap that exact difference.
10. for each age-standardized state statistic, common-age statistic, component interaction, and reference age-gap reduction, retain only resamples with every required Q1/Q5 age cell present; report `n_draws` and `valid_draw_fraction`, and require `valid_draw_fraction >= 0.98` (at least 4,900 of 5,000 canonical draws) for mechanism-label eligibility.

Repeat the same pooled, state-specific-age and common-age decomposition for frozen equal-weight `compression_score` as a reference only. For the age-composition diagnostic define `raw_direction_gap = DOWN pooled Q5−Q1 − UP pooled Q5−Q1`, `common_age_direction_gap` analogously, and `age_gap_reduction_fraction = 1 − abs(common_age_direction_gap)/abs(raw_direction_gap)`; it is undefined if the raw gap is zero.

No model selection and no feature winner is promoted.

## 5. Predeclared mechanism labels

### COMPONENT_COHERENT_DIRECTION_ASYMMETRY

This label applies only if:

- CURRENT_DOWN has at least 3/4 components whose age-standardized Q5−Q1 is positive, whose bootstrap 95% CI lower bound is >0, whose bootstrap valid-draw fraction is at least 0.98, and whose yearly sign is positive in at least 2/3 years;
- CURRENT_UP has at most 1/4 component meeting all three conditions;
- at least two component `DOWN−UP` interaction bootstrap CIs have lower bound >0 and valid-draw fraction at least 0.98.

### AGE_COMPOSITION_DOMINANT

Applies only if the common-age reweighting reduces the frozen reference-score DOWN−UP Q5−Q1 gap by at least 50%, the reference age-gap-reduction bootstrap valid-draw fraction is at least 0.98, and the component-coherent label is false.

### MIXED_OR_INCONCLUSIVE

All other outcomes.

These are mechanism labels on exposed development evidence, not new scientific support.

## 6. Hard prohibitions

Issue #647 may not introduce:

- P128 / P256 / C1 / C2 / C3;
- any other-frequency context;
- any future-state predictor as input;
- new feature families;
- alternate age bins;
- alternate horizons;
- threshold search;
- PnL / exit policy / routing / trade optimization.

It may not reclassify #624 as supported and may not create a DOWN-only trading rule.

## 7. Stop rule

If this fixed audit is mixed/inconclusive, close #647 without adding a feature zoo.

If it yields a coherent mechanism, that mechanism may motivate a **separate** preregistered predictive hypothesis. Nothing in #647 itself grants signal, router, trade, paper, live, or production authority.
