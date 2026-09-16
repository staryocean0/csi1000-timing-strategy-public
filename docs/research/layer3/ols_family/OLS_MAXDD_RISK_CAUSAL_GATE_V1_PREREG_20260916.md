# OLS Layer3 — Risk-state causal entry gate v1

Profile to be implemented only if activated: `ols-maxdd-risk-causal-gate-v1`

Status: **PREREGISTERED BEFORE RISK-OVERLAP VERDICT REVEAL**

Authority parent: `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.
Diagnostic parent under execution: standard public run `35060072956-1`, profile `ols-maxdd-risk-state-overlap-v1`.

This document freezes the next causal-identification question before the parent overlap result is read. It grants no intervention or production authority.

## 1. Activation gate

This study may execute only if all of the following are true:

1. run `35060072956-1` completes successfully and is independently verified;
2. its frozen `relationship_verdict` is exactly `STRONG`;
3. the verified result preserves `reliability_used_as_market_state=false`, `state_machine_authority=false`, and `production_authority=false`;
4. the Risk state source/model/data identities remain those pinned by `ols-maxdd-risk-state-overlap-v1`.

If the parent verdict is `CONDITIONAL`, `WEAK`, or `INSUFFICIENT_SUPPORT`, this risk-state-only causal gate is **not** executed. `CONDITIONAL` specifically means the joint descriptive signal, not Risk state alone, carried the evidence; because the current morphology percentiles are retrospective descriptive features, they may not be silently converted into a causal trading rule.

## 2. Research question

> At the causal OLS decision close immediately before a new executable non-flat baseline segment, does the already-observable Risk Tool market state consistently identify segments that will extend the existing strategy drawdown?

This is an identification question only. It does not suppress trades, resize positions, accelerate exits, add cooldowns, or change the OLS lifecycle.

## 3. Frozen baseline universe

- Symbol `000852.SH`.
- Years 2020–2025 only; no fresh-OOS claim.
- Same pinned 5m carrier, OLS private source, W12/W24 competition and five exit families used by D0 / Failure Atlas / Risk-overlap v1.
- Exit families: `qualification_reset`, `first_opposite_close`, `two_opposite_closes`, `prior_extreme_break`, `frozen_midline_break`.
- Segment definition is inherited exactly from Phase B: a maximal consecutive run of the same non-zero executable position.
- If a segment begins on executable 15m bar `t`, the causal snapshot is decision close `t-1`.

## 4. Frozen causal Risk feature

There is exactly one primary candidate:

`risk_active_at_decision`

- `1` iff the Risk Tool state observable at decision close `t-1` is `UNSAFE` or `RECOVERING`;
- `0` iff it is `NORMAL`.

No reliability band is used. `LOW/MID/HIGH` reliability remains forbidden as a market-risk label.

Time alignment is physical and causal:

- map the 15m decision close to its final constituent native 5m bar using the verified same-carrier trading-day/bar-order identity;
- use only the Risk state available at that 5m bar end;
- never use a later 5m state, future recovery outcome, or future `recovery_probability` realization.

`recovery_probability_30m` is not a primary candidate in this gate. It is a probability of recovery to NORMAL, not a high-risk probability.

## 5. Frozen adverse outcome

Reuse the Phase-B primary outcome **without modification**:

`future_drawdown_extension`

For each natural frozen-baseline segment:

1. measure strategy drawdown at the segment execution point;
2. follow only that naturally occurring frozen-baseline segment;
3. measure the worst strategy drawdown reached during that segment;
4. `future_drawdown_extension = max(0, |worst future drawdown| - |drawdown at execution|)`.

Secondary descriptive outcomes: segment maximum adverse excursion, segment gross return, and whether the segment sets a new deeper equity trough.

## 6. Primary eligible universe

To remain comparable with Phase B and to test drawdown amplification rather than ordinary entry selection, the promotion universe is exactly:

- baseline segment is an underwater re-entry;
- `lagged_drawdown_abs_at_decision > 0`;
- `reentry_ordinal_since_hwm >= 1`;
- `risk_active_at_decision` is observed;
- outcome is finite.

The study must also report all-segment descriptive results, but those cannot pass the gate by themselves.

## 7. Frozen analyses

For each of the five exit families report on the primary eligible universe:

- expected-risk-direction Spearman association between `risk_active_at_decision` and `future_drawdown_extension`;
- rank AUC for identifying the worst 20% of `future_drawdown_extension`;
- counts of Risk-active and NORMAL rows;
- mean/median future drawdown extension by Risk state;
- per-year association for sufficient family-year cells;
- sign stability across years.

The worst-20% outcome label is evaluation-only and is not a trading threshold.

## 8. Frozen causal promotion gate

Reuse the already frozen Phase-B causal-identification thresholds exactly. `risk_active_at_decision` becomes `RISK_PHASE_C_ELIGIBLE` only if all conditions hold:

1. expected-risk-direction Spearman `rho >= 0.25` in at least 3 of 5 exit families;
2. association is positive in at least 4 of 5 exit families;
3. median family AUC for the worst-20%-extension label is at least `0.60` across sufficient families;
4. at least `70%` of sufficient family-year cells have a positive association;
5. independent verification proves the feature was available at decision close `t-1`.

Sufficiency is inherited from Phase B:

- family correlation/AUC: at least 20 eligible rows and both binary feature values present;
- family-year sign cell: at least 10 eligible rows and both binary feature values present.

If any gate condition fails, `risk_phase_c_authority=false` and no Risk-conditioned OLS intervention may be executed from this lane.

## 9. Anti-rescue boundaries

This study must not:

- search a Risk threshold;
- split `RECOVERING` from `UNSAFE` to rescue a failed result;
- use reliability bands as Risk states;
- optimize probability thresholds;
- introduce morphology thresholds after seeing the overlap result;
- change the Phase-B outcome or causal unit after reveal;
- choose an exit family by performance;
- change OLS entries/exits/position size;
- claim fresh OOS.

A failed gate is authoritative for this exact `risk_active_at_decision` formulation.

## 10. Required outputs

- `segment_entry_table.csv`
- `risk_candidate_summary.csv`
- `year_stability.csv`
- `RESULTS.json`
- `RESULTS.md`

The required result must state `risk_phase_c_authority` explicitly and must keep production/trading authority false.
