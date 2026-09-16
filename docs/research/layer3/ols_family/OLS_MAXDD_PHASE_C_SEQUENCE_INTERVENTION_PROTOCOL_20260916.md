# OLS Layer3 — MaxDD Phase C sequence intervention comparison

Profile: `ols-maxdd-phase-c-sequence-intervention-v1`

Status: **PREREGISTERED BEFORE INTERVENTION OUTCOME REVEAL**

Authority parent: `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.
Scientific parent: verified sequence-hazard run `35043295079-1` with `phase_c_reopen_authority=true`.

## 1. Research objective

Test whether the two preregistered sequence-hazard candidates that passed the causal identification gate can be converted into a **bounded risk-control overlay** that materially reduces MaxDD and tail drawdown while preserving an explicit gross-return floor.

This is a research A/B comparison. It does not install a production rule.

## 2. Frozen baseline

- Symbol `000852.SH`, years 2020–2025, no fresh-OOS claim.
- Same frozen OLS entry mechanics, W12/W24 competition, data identities and five exit families as D0–sequence-hazard v1.
- Baseline gross strategy returns and segment/episode calendar are replayed unchanged.
- Intervention triggers are computed only from information available at the sequence-hazard decision close.
- Trigger episodes and intervention calendars are defined from the **frozen baseline path**, not recomputed from intervention equity. This prevents feedback-driven trigger drift and preserves deterministic A/B attribution.

## 3. Frozen trigger constructions

Only the two sequence-hazard-v1 eligible features may be used.

### A. `direction_flip`
Trigger when the two completed natural baseline segments immediately preceding the sequence checkpoint have opposite executable directions.

### B. `pe_collapse_ge_0p30`
Trigger when `seq_pe_collapse_burden >= 0.30` at the two-segment checkpoint.

The threshold 0.30 is not selected from intervention outcomes. It is anchored to the pre-existing frozen OLS path-efficiency qualification threshold of 0.30.

### C. `both`
`direction_flip AND pe_collapse_ge_0p30`.

### D. `either`
`direction_flip OR pe_collapse_ge_0p30`.

No other trigger threshold or feature combination may be searched in this study.

## 4. Frozen action ladder

Actions begin at the naturally scheduled next executable baseline segment after the causal checkpoint.

1. `half_next_segment` — multiply frozen baseline strategy returns by 0.5 only for that next natural non-flat segment.
2. `block_next_segment` — replace frozen baseline strategy returns by 0 only for that next natural non-flat segment.
3. `block_until_baseline_recovery` — replace frozen baseline strategy returns by 0 from that next natural segment start through the end of the frozen baseline drawdown episode. This action is tested only with the `either` trigger as a risk-control upper bound.

After the affected calendar ends, returns revert to the frozen baseline path. The study does not alter baseline qualification, exit formulas, segment boundaries, or future trigger computation.

## 5. Frozen variants

Primary comparison set:

- `direction_flip__half_next_segment`
- `direction_flip__block_next_segment`
- `pe_collapse_ge_0p30__half_next_segment`
- `pe_collapse_ge_0p30__block_next_segment`
- `both__half_next_segment`
- `both__block_next_segment`
- `either__half_next_segment`
- `either__block_next_segment`
- `either__block_until_baseline_recovery`

No same-run threshold, duration, size, or trigger search is permitted.

## 6. Required metrics per exit family and variant

- baseline and intervention total gross return;
- gross-return retention = intervention total return / baseline total return when baseline return is positive;
- baseline and intervention MaxDD;
- relative MaxDD depth improvement;
- baseline and intervention mean worst-20 drawdown-episode depth;
- relative worst-20 tail improvement;
- baseline/intervention non-flat-equivalent exposure bars and exposure reduction;
- affected sequence checkpoints and affected baseline segments;
- fraction of removed/reduced baseline segment returns that were positive;
- median removed/reduced baseline segment gross return;
- calendar overlap audit ensuring each bar receives at most the strongest preregistered action for a given variant.

Also report annual gross return and annual MaxDD by family/variant descriptively. Annual results do not independently grant authority.

## 7. Frozen candidate gate

A variant becomes `PHASE_D_RETURN_RECOVERY_ELIGIBLE` only if all conditions hold:

1. relative MaxDD depth improvement >= 20% in at least 3 of 5 exit families;
2. mean worst-20 drawdown depth improvement >= 10% in at least 3 of 5 families;
3. gross-return retention >= 80% in at least 4 of 5 families;
4. no exit family has MaxDD relative depth worsening worse than 5%;
5. for `frozen_midline_break`, MaxDD improvement >= 20% and gross-return retention >= 70%;
6. causal trigger construction and deterministic intervention calendar are independently verified.

`phase_d_authority=true` only if at least one frozen variant passes all six conditions.

If multiple variants pass, the study may report a **research ordering** only by this fixed lexicographic priority: median MaxDD improvement, then median worst-20 improvement, then median gross-return retention. This ordering grants no production authority.

## 8. Interpretation boundaries

- MaxDD is the first objective; return is a constraint and secondary objective.
- Transaction costs are not included in this first gross intervention comparison. A passing result only authorizes a separately preregistered cost/robustness or return-recovery phase.
- 2020–2025 are consumed research years.
- A failed variant may not be rescued by changing PE thresholds, exposure fractions, cooldown lengths, or trigger combinations after outcome reveal.
- No production, routing, leverage, deployment, or live-trading authority is granted.

## 9. Required outputs

- `RESULTS.json`
- `variant_summary.csv`
- `annual_summary.csv`
- `trigger_audit.csv`
- `RESULTS.md`
