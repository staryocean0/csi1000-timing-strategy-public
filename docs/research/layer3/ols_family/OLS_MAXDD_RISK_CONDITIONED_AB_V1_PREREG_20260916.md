# OLS Layer3 — Plain OLS vs Risk-conditioned OLS A/B v1

Profile to be implemented only after causal authorization: `ols-maxdd-risk-conditioned-ab-v1`

Status: **PREREGISTERED BEFORE RISK-OVERLAP VERDICT AND BEFORE CAUSAL-GATE OUTCOME REVEAL**

Authority parent: `OLS_MAXDD_RESEARCH_CHARTER_20260915.md`.
Upstream diagnostic under execution: `35060072956-1` / `ols-maxdd-risk-state-overlap-v1`.
Required causal parent if activated: `ols-maxdd-risk-causal-gate-v1` as frozen in `OLS_MAXDD_RISK_CAUSAL_GATE_V1_PREREG_20260916.md`.

This document freezes the final research A/B before either parent result is used to choose action details. It grants no current intervention or production authority.

## 1. Execution activation gate

This A/B may execute only if:

1. the Risk-overlap parent completes verified with `relationship_verdict=STRONG`;
2. the separately preregistered `ols-maxdd-risk-causal-gate-v1` subsequently completes verified with `risk_phase_c_authority=true` for the one frozen candidate `risk_active_at_decision`;
3. all source/carrier identities remain pinned to the same OLS/Risk research lineage;
4. no parent result has been used to change this action, metric set, or success gate.

If either upstream gate fails, this A/B is not run and is not rescue-modified.

A `CONDITIONAL` overlap verdict does not activate this study because the existing joint morphology score is retrospective/descriptive and has no causal trading threshold. A separate causal morphology study would be required rather than silently reinterpreting `J` as an executable rule.

## 2. Research objective

Compare the frozen Plain OLS baseline with one fixed, causally observable Risk-conditioned overlay whose only purpose is to reduce maximum and tail drawdown while preserving the predeclared gross-return floor.

Primary objective: MaxDD reduction.
Secondary objective: return retention after risk reduction.

This is a research A/B, not a production rule.

## 3. Frozen baseline

For each of the five exit families independently:

- symbol `000852.SH`, years 2020–2025;
- same pinned data and OLS source as D0 and Risk-overlap v1;
- same W12/W24 entry mechanics and natural OLS lifecycle;
- same five baseline exit families;
- same gross open-to-open return convention;
- no transaction-cost or fresh-OOS claim.

`PLAIN_OLS` is replayed byte-for-semantics from the frozen baseline path.

## 4. Frozen Risk-conditioned variant

There is exactly one intervention variant:

`RISK_ACTIVE__BLOCK_NEXT_NATURAL_SEGMENT`

At the causal decision close immediately preceding each natural baseline non-flat segment:

- if `risk_active_at_decision == 0`, leave the natural baseline segment unchanged;
- if `risk_active_at_decision == 1`, replace frozen baseline strategy returns by `0` for the **entire next natural baseline non-flat segment**;
- when that frozen natural segment ends, returns revert to the frozen baseline path.

This is the charter's `block new entry/addition` action expressed as a deterministic A/B overlay.

Important implementation boundary: the intervention calendar is built from the frozen baseline segment calendar and the causal Risk state at its decision close. It is **not recomputed from intervention equity**. OLS qualification, exit formulas, segment endpoints, subsequent OLS signals, and Risk state construction remain unchanged. This preserves deterministic attribution and prevents feedback-driven trigger drift.

No `UNSAFE`/`RECOVERING` split, probability threshold, cooldown, half-size alternative, faster-exit alternative, duration search, or exit-family-specific rule is allowed in this study.

## 5. Frozen causal timing

If the natural executable segment begins on 15m bar `t`, the decision close is `t-1`.

`risk_active_at_decision` must be taken from the Risk Tool state observable at the final constituent native 5m bar of decision close `t-1`, using the already verified physical same-carrier mapping. No future Risk state or recovery outcome may be used.

## 6. Required metrics per exit family

For `PLAIN_OLS` and `RISK_ACTIVE__BLOCK_NEXT_NATURAL_SEGMENT` report:

- total gross return;
- final gross equity;
- gross-return retention = conditioned total return / plain total return when plain return is positive;
- MaxDD;
- relative MaxDD depth improvement;
- mean worst-20 drawdown-episode depth;
- relative worst-20 tail improvement;
- non-flat-equivalent exposure bars and exposure reduction;
- count and share of natural segments blocked;
- fraction of blocked baseline segments whose original gross return was positive;
- median blocked baseline segment gross return;
- exact intervention-calendar overlap audit.

Also report annual gross return and annual MaxDD descriptively for every family. Annual results cannot independently pass the study.

## 7. Frozen A/B success gate

Reuse the already preregistered Phase-C risk-first intervention gate **without changing thresholds**. The Risk-conditioned variant becomes `RISK_CONDITIONED_PHASE_D_ELIGIBLE` only if all conditions hold:

1. relative MaxDD depth improvement >= 20% in at least 3 of 5 exit families;
2. mean worst-20 drawdown depth improvement >= 10% in at least 3 of 5 families;
3. gross-return retention >= 80% in at least 4 of 5 families;
4. no exit family has MaxDD relative depth worsening worse than 5%;
5. for `frozen_midline_break`, MaxDD improvement >= 20% and gross-return retention >= 70%;
6. causal Risk trigger construction and deterministic intervention calendar are independently verified.

These thresholds are inherited from `OLS_MAXDD_PHASE_C_SEQUENCE_INTERVENTION_PROTOCOL_20260916.md`; they are not chosen from Risk-conditioned outcomes.

If the gate fails, `risk_conditioned_phase_d_authority=false`. The exact variant may not be rescued by changing states, probability cutoffs, morphology thresholds, durations, sizing, or exit families after reveal.

## 8. Anti-overfitting and interpretation boundaries

- MaxDD is first; return is a constraint and secondary objective.
- All five exit families must be shown; no single-family winner can authorize the overlay.
- 2020–2025 are consumed research years.
- No transaction costs are included in this first bounded A/B.
- No fresh OOS claim is permitted.
- A pass authorizes only the next separately governed robustness/return-recovery research phase; it does not install live routing, leverage, sizing, or production behavior.
- A failure is authoritative for this exact Risk-active block-next-natural-segment formulation.

## 9. Required outputs

- `RESULTS.json`
- `family_ab_summary.csv`
- `annual_summary.csv`
- `intervention_audit.csv`
- `RESULTS.md`

`RESULTS.json` must explicitly report `risk_conditioned_phase_d_authority`, `production_authority=false`, and `fresh_oos_claimed=false`.
