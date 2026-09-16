# OLS Layer3 — MaxDD sequence-hazard identification protocol

Profile: `ols-maxdd-sequence-hazard-v1`

Status: **PREREGISTERED BEFORE OUTCOME REVEAL**

Authority parent: `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.
Scientific parents: Phase A run `34978764073-1` and negative Phase B run `35040712447-1`.

## 1. Why this study exists

Phase A showed that severe drawdowns are concentrated in a small number of episodes and that repeated participation is associated with episode depth. Phase B then rejected the frozen single-entry snapshot candidates as reliable predictors of which next segment will extend drawdown. This study therefore changes the causal unit from one re-entry snapshot to a **state-path prefix** while preserving the same frozen OLS baseline and MaxDD-first objective.

This study does not rescue-tune any failed Phase-B candidate and does not change trading.

## 2. Primary question

> After an underwater drawdown episode has already completed two natural baseline segments, can the causal path prefix identify whether the still-open episode is likely to extend materially deeper before equity recovers its pre-episode high-water mark?

## 3. Frozen baseline universe

- Symbol: `000852.SH`.
- Research years: 2020–2025; no fresh-OOS claim.
- Frozen OLS entry mechanics, W12/W24 competition and five exit families are unchanged.
- Gross zero-cost semantics are unchanged.
- Same pinned private OLS source and fixed public 5m data identities as D0/D1/D2/Phase A/Phase B.

A drawdown episode starts when frozen strategy equity first moves below its running high-water mark and ends at the first later bar at which that same high-water mark is recovered or exceeded. Final right-censored episodes that do not recover before sample end are excluded from the primary gate but reported descriptively.

## 4. Primary causal checkpoint

Each recovered episode contributes at most one primary row.

The primary checkpoint is the decision close immediately before the first new executable segment that begins after **two completed non-flat segments** have already occurred within the same still-underwater episode. If no such checkpoint exists, the episode is not primary-eligible.

All features use only information available by that decision close. This one-row-per-episode design prevents long bad episodes from receiving extra statistical weight merely because they contain many re-entries.

A preregistered sensitivity repeats the construction after three completed episode segments. The three-segment sensitivity cannot independently grant intervention-study authority.

## 5. Frozen sequence candidates

All expected-risk directions are higher value = higher remaining drawdown risk.

For the two completed segments immediately preceding the primary checkpoint:

1. `seq_loss_burden` — sum of `max(0, -segment_return_gross)`.
2. `seq_mae_burden` — sum of segment maximum adverse excursion.
3. `seq_r2_collapse_burden` — sum of within-segment peak-to-current fit-R² collapse.
4. `seq_pe_collapse_burden` — sum of within-segment peak-to-current path-efficiency collapse.
5. `seq_loss_acceleration` — second-segment loss magnitude minus first-segment loss magnitude.
6. `seq_r2_collapse_acceleration` — second R²-collapse magnitude minus first.
7. `seq_pe_collapse_acceleration` — second PE-collapse magnitude minus first.
8. `seq_participation_density` — completed segment count divided by bars from the first prefix-segment start through the checkpoint decision bar.
9. `seq_direction_flip` — 1 when the two completed segments have opposite executable directions, else 0.

The three-segment sensitivity uses the same burden/density definitions over the last three completed segments; acceleration is last-segment damage minus the mean damage of the preceding two; direction flip is the fraction of adjacent direction changes.

## 6. Primary outcome

At the checkpoint, record causal drawdown depth relative to the episode high-water mark. Follow the frozen baseline until that episode recovers. The primary adverse outcome is:

`remaining_episode_drawdown_extension = max(0, eventual_episode_trough_depth - checkpoint_drawdown_depth)`.

Secondary outputs: eventual full episode depth, bars to trough, bars to recovery, future segment starts before recovery, and whether the eventual trough occurs after the checkpoint.

The worst 20% of remaining extension within each exit family is an evaluation label only, not a trading threshold.

## 7. Analysis and frozen promotion gate

For each candidate and exit family report family Spearman rho, rank AUC for the worst-20% label, and per-year rho for sufficient cells. Primary family statistics use only the one-row-per-episode two-segment checkpoint table.

A candidate becomes `PHASE_C_REOPEN_ELIGIBLE` only if all conditions hold:

1. primary rho >= 0.25 in at least 3 of 5 exit families;
2. primary rho has the expected positive sign in at least 4 of 5 families;
3. median family AUC >= 0.60 across sufficient families;
4. at least 70% of sufficient family-year cells have positive rho;
5. in the preregistered three-segment sensitivity, rho is positive in at least 4 of 5 sufficient families;
6. causal availability at the checkpoint is independently verified.

`phase_c_reopen_authority=true` only if at least one frozen candidate passes all six conditions. Passing authorizes only a separately preregistered intervention comparison; it does not install a rule or grant production authority.

## 8. Sufficiency

- Primary family rho/AUC: at least 20 recovered primary-eligible episodes and at least two distinct candidate values.
- Family-year rho: at least 8 primary-eligible episodes and at least two distinct candidate values.
- Three-segment sensitivity family rho: at least 15 recovered eligible episodes and at least two distinct candidate values.
- Missing/non-finite path features are not imputed.

## 9. Anti-overfitting boundaries

This study must not search sequence lengths, R²/PE thresholds, cooldowns, sizing, holding periods, feature weights, or PnL-ranked combinations. Sequence length 2 is primary and length 3 is the only frozen sensitivity. Entry/exit formulas and all realized baseline trades remain unchanged. Negative findings are authoritative.

## 10. Required outputs

- `episode_checkpoint_table.csv`
- `candidate_summary.csv`
- `year_stability.csv`
- `seq3_sensitivity.csv`
- `RESULTS.json`
- `RESULTS.md`

No production or trading authority is granted.