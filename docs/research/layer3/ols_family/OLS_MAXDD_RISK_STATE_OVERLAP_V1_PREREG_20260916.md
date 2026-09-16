# OLS Layer3 — MaxDD Failure × Volatility / Risk-State Overlap v1 preregistration

Profile to be wired after this preregistration is frozen: `ols-maxdd-risk-state-overlap-v1`

Status: `FROZEN_BEFORE_EXECUTION_WIRING`

Date: 2026-09-16

## 1. Scientific question

This is a diagnostic-only study. It asks:

> When the frozen CSI1000 OLS strategy suffers its deepest drawdown episodes, what repeatable 5-minute K-line risk state is the market in, and is that state materially the same thing as the existing Risk Tool V2 volatility/risk state?

The study must classify the relationship as `STRONG`, `CONDITIONAL`, or `WEAK` only after the frozen diagnostics below are computed. It does not design a filter, state machine, entry/exit overlay, cooldown, sizing rule, threshold, leverage rule, or production route.

MaxDD reduction remains the project priority, but this study grants no trading authority.

## 2. Frozen OLS authority

- Symbol: `000852.SH`
- Years: 2020–2025
- Market-data repository/ref: `staryocean0/factorlab-trend-reversion-regime-lab@1d760ea9525eb3688b70a4aa0f2b5b207af16a17`
- Frozen private OLS source ref: `67effb80f51228f6129dca5c4f7971a0bb6c7f15`
- Failure-label parent protocol: `docs/research/layer3/ols_family/OLS_MAXDD_FAILURE_ATLAS_V1_PROTOCOL_20260915.md`
- Failure-label authority run: `34978764073`, private run `runs/public-research/34978764073-1`
- Top-tail definition: the same top-20 drawdown episodes per exit family used by Failure Atlas v1.
- Exit families remain exactly:
  - `qualification_reset`
  - `first_opposite_close`
  - `two_opposite_closes`
  - `prior_extreme_break`
  - `frozen_midline_break`

The study must replay the frozen D0/Failure-Atlas semantics and verify the resulting episode identities/counts before using any overlap metric. Entry, exit, position, sizing, and PnL formulas may not change.

OLS operates on 15-minute bars constructed deterministically from the frozen 5-minute carrier. Failure labels therefore remain 15-minute OLS episode labels; the risk/morphology measurements inside each label are taken from the constituent native 5-minute bars.

## 3. Frozen Risk Tool V2 semantics

The Risk Tool fields are semantically separated as follows.

### 3.1 Market-risk state

Frozen source used to reconstruct state rows:

- private ref: `3879de41a5ac7c12246b811f51d16dc8586b9dae`
- path: `runtime/research/risk_tool_v2_severity_persistence_v1/run_study.py`
- Git blob SHA1: `7a9f238442f5a4836c6f38dcafec4bc34526fc5c`

The true market-state field is `risk_state`, with categories:

- `NORMAL`
- `UNSAFE`
- `RECOVERING`

The frozen sensor semantics are not to be retuned:

- 5-minute log return within trading day;
- `rv12`: 12-return rolling standard deviation;
- `bg_vol48`: lagged 48-return background standard deviation;
- `vol_ratio = rv12 / bg_vol48`;
- `shock_intensity = abs(ret_5m) / bg_vol48`;
- shock if `shock_intensity >= 3.00`;
- `UNSAFE` persistence threshold `vol_ratio >= 1.50`;
- `RECOVERING` while `1.10 < vol_ratio < 1.50` following an unsafe state;
- `NORMAL` when recovery reaches `vol_ratio <= 1.10`, subject to the frozen transition function.

Primary risk-state indicator for overlap diagnostics:

`risk_indicator = 1[risk_state in {UNSAFE, RECOVERING}]`.

`unsafe_indicator = 1[risk_state == UNSAFE]` is reported separately.

### 3.2 Recovery probability, not high-risk probability

The probability output is `recovery_probability`: the probability of returning to `NORMAL` within the stated horizon while already in the Risk Tool primary risk cohort. It is **not** a probability of entering a high-risk state.

The primary probability diagnostic uses the frozen 30-minute recovery component because the existing authority map marks the 30-minute probability component complete. The frozen model/calibration inputs are:

- Phase-1 model freeze: private release `388319643`, asset `563182909`, archive SHA256 `c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b`, member `study/MODEL_FREEZE.json`, member SHA256 `b81cae6208d96890c0fd83d47e4ea8c8a81ba55b41c78f58db29e9160f173551`.
- Phase-1b calibration freeze: private release `388398729`, asset `563403877`, archive SHA256 `197c15aaa725a20cbfd7b07ff639e59c400b38eaa49c0141fa6fca9d035dd3fc`, member `study/CALIBRATION_FREEZE.json`, member SHA256 `74ecd25790123f026e29cba7bb84322aad8a385c10fe3d60ef0d75d52d1b1909`.

For cohort rows, the study may report calibrated 30-minute recovery probability from the frozen challenger representation. Lower recovery probability means slower/less likely recovery; no inversion may be relabeled as a high-risk probability.

Probability is undefined outside its eligible primary-cohort rows. Missing probability must remain missing; ordinary bars may not be imputed as normal-risk, zero risk, or probability 0/1.

The 15-minute probability/reliability output is secondary only. It may be reported only if the exact current frozen transform and reliability scorer are pinned in the execution broker. It may not affect the relationship verdict in v1.

### 3.3 Reliability is not market risk

`reliability_score` and derived `reliability_band` (`LOW` / `MID` / `HIGH`) describe reliability of the probability output. They are not volatility buckets and are prohibited from being used as market-risk state, volatility state, or a verdict input.

## 4. Native 5-minute realized-volatility panel

Raw OHLC diagnostics are computed independently of Risk Tool state from the same frozen 5-minute `000852.SH` carrier.

For every valid bar, compute at minimum:

- `ret_5m = log(close_t / close_{t-1})` within trading day;
- `abs_ret_5m = abs(ret_5m)`;
- `intrabar_log_range = log(high / low)`;
- normalized true range, with overnight gaps excluded and the first bar of a trading day using high-low only;
- `atr12_norm`: 12-bar rolling mean normalized true range;
- `rv12_rms = sqrt(mean(ret_5m^2))` over the trailing 12 valid 5-minute returns;
- Risk Tool's frozen `rv12`, `bg_vol48`, `vol_ratio`, and `shock_intensity` as a separate semantic panel.

For `rv12_rms`, compute both the continuous value and its full-year retrospective empirical percentile among all valid 5-minute bars in the same calendar year. The retrospective percentile is descriptive only and makes no live/PIT claim.

Freeze the descriptive volatility buckets at within-year empirical terciles:

- `LOW_VOL`: percentile < 1/3;
- `NORMAL_VOL`: 1/3 <= percentile < 2/3;
- `HIGH_VOL`: percentile >= 2/3.

No bucket boundary may be moved after seeing OLS failure results.

## 5. Directionality, whipsaw, and multi-scale morphology panel

For trailing windows of 12, 24, and 48 native 5-minute returns, compute without parameter search:

- path efficiency: `abs(sum(ret)) / sum(abs(ret))`;
- net displacement;
- total path length;
- sign-reversal density among consecutive non-zero returns;
- directional sign of net displacement.

The primary local-vs-long morphology uses:

- local directionality: `PE12`;
- longer-scale directionality: `PE48`;
- whipsaw density: `REV48`.

For each calendar year, convert `PE12`, `PE48`, and `REV48` to full-year retrospective empirical percentiles. These are descriptive morphology ranks, not live thresholds.

Freeze the per-bar morphology score before execution:

`M_bar = PE12_percentile * (1 - PE48_percentile) * REV48_percentile`.

This score is deliberately highest when a short window looks directionally efficient while the longer path is inefficient and reversal-dense. It tests the stated 'local trend looks good but the larger-scale market repeatedly reconstructs direction' hypothesis without fitting weights.

For every OLS episode, define:

- `M_episode = median(M_bar)` from episode start through trough;
- `R_episode = mean(risk_indicator)` from episode start through trough;
- `U_episode = mean(unsafe_indicator)` from episode start through trough;
- `J_episode = median(risk_indicator * M_bar)` from episode start through trough.

`J_episode` is diagnostic only. It is not a candidate trading score.

The report must also present explicit state cells using the fixed within-year terciles, including at minimum:

- high-vol + high-PE48 (high-vol trend);
- high-vol + low-PE48 (high-vol chop);
- normal-vol + low-PE48;
- low-vol + low-PE48;

and split each by high/not-high `REV48` tercile where support exists. This table is required so that 'high volatility' cannot be equated with 'OLS failure'.

The 12/24/48 panel is the minimum scale check for this v1 overlap study. Full trajectory normalization, bar aggregation at 10m/15m/30m/60m, DTW, and clustering remain a later morphology study and receive no authority here.

## 6. Episode and pre-failure windows

For every Failure Atlas episode:

- `episode_window`: OLS episode start through trough, inclusive;
- `pre12`: 12 native 5-minute market bars immediately preceding the first constituent 5-minute bar of the OLS start bar;
- `pre48`: 48 native 5-minute market bars immediately preceding the same anchor.

Market bars, not wall-clock minutes, define these lookback counts.

Required episode summaries include medians/means and occupancy for the raw-vol, state, and morphology panels above.

For risk-state lead diagnostics, report the number of market bars from the most recent transition from `NORMAL` into `{UNSAFE, RECOVERING}` within `pre48` to the episode start. If no such transition occurs, leave lead missing and report the no-transition count.

For 30-minute recovery probability, report coverage and distribution on eligible cohort rows in `pre48` and `episode_window`. Because lower recovery probability denotes worse persistence, report the signed late-minus-early change explicitly; do not describe it as a rising high-risk probability.

## 7. Controls

No control may be chosen after reviewing overlap results.

For each exit family, report top-tail episodes against all of the following:

1. `NON_TOP_DD`: all drawdown episodes not in that family's frozen top-20;
2. `PROFITABLE_POSITION_SEGMENT`: all maximal same-direction non-flat baseline position segments with positive cumulative frozen strategy return, excluding any bars that overlap a top-tail episode start-to-trough window;
3. `FLAT_MARKET`: all 15-minute baseline bars with executable position zero, expanded to their constituent 5-minute bars, excluding any top-tail episode start-to-trough overlap.

The top-tail versus `NON_TOP_DD` episode comparison is the primary verdict comparison. The other controls are descriptive guardrails against concluding that a common market state is uniquely associated with failure.

All summaries must be shown:

- by exit family;
- by calendar year 2020, 2021, 2022, 2023, 2024, 2025;
- pooled only as a descriptive supplement, because the five exit families may label overlapping market intervals.

A year is evaluable for AUC-based stability only when it contains at least 2 top-tail episodes and at least 20 non-top episodes across the five-family episode table. Non-evaluable years remain reported but do not count as stability passes.

## 8. Primary diagnostic statistics

Top-tail is the positive class and `NON_TOP_DD` is the negative class.

Without fitting any parameters, compute AUC for:

- `R_episode` (Risk Tool state occupancy; risk-only);
- `U_episode` (UNSAFE-only occupancy; sensitivity);
- episode median `rv12_rms` within-year percentile (raw-vol-only);
- `M_episode` (morphology-only);
- `J_episode` (Risk Tool state × morphology interaction).

Compute family-level AUCs for each of the five exit modes and year-level AUCs for evaluable years. Ties use average ranks. Report bootstrap confidence intervals as descriptive uncertainty only; they do not replace the frozen verdict rules below.

Also report, without winner selection:

- median differences top-tail minus controls;
- Risk Tool state occupancy by volatility × directionality cells;
- recovery-probability coverage and quantiles;
- pre12/pre48 state occupancy;
- risk-state transition lead distributions;
- family/year support counts;
- top-tail exposure share in high-vol trend versus high-vol chop.

No p-value, confidence interval, cell, or metric may be used post hoc to redefine the verdict thresholds.

## 9. Frozen relationship verdict

The verdict is about whether **Risk Tool information is worth carrying into a later OLS state-machine research stage**, not about whether any filter should be traded.

### `STRONG`

Return `STRONG` only if all are true:

1. median of the five family-level AUCs for `R_episode` is at least 0.65;
2. at least 4 of 5 exit families have `R_episode` AUC at least 0.60;
3. at least 4 calendar years are evaluable, and at least 4 evaluable years have `R_episode` AUC at least 0.60;
4. no evaluable year has `R_episode` AUC below 0.45.

Interpretation: the existing Risk Tool market-risk state itself has materially stable overlap with OLS top-tail failure. A later Risk-state × OLS-state-machine study may be proposed, but no hard filter is authorized.

### `CONDITIONAL`

Evaluate this only if `STRONG` fails. Return `CONDITIONAL` only if all are true:

1. median family-level AUC for `J_episode` is at least 0.65;
2. at least 4 of 5 families have `J_episode` AUC at least 0.60;
3. median across families of `AUC(J_episode) - max(AUC(R_episode), AUC(M_episode))` is at least 0.05;
4. at least 4 calendar years are evaluable and at least 4 evaluable years have `J_episode` AUC at least 0.60;
5. median across evaluable years of `AUC(J_episode) - max(AUC(R_episode), AUC(M_episode))` is at least 0.03.

Interpretation: Risk Tool state alone is insufficient, but Risk Tool state adds material, stable information when conditioned on the pre-registered whipsaw morphology. Risk Tool may be retained only as one dimension of a later state-machine study.

### `WEAK`

Return `WEAK` when neither `STRONG` nor `CONDITIONAL` passes, provided at least 4 years are evaluable and all five exit families contain the frozen top-20 set.

Interpretation: do not connect Risk Tool to OLS on the evidence from this study. Continue with K-line morphology / multi-scale failure-state research instead.

If the support prerequisites for any of the three verdicts fail because data/episode support is insufficient, return `INSUFFICIENT_SUPPORT` rather than forcing a relationship claim.

## 10. Required outputs

Private authoritative outputs must include at least:

- `study/RESULTS.json`
- `study/RESULTS.md`
- `study/episode_overlap.csv`
- `study/family_auc.csv`
- `study/year_auc.csv`
- `study/vol_directionality_cells.csv`
- `study/pre_failure_lead.csv`
- `study/recovery_probability_summary.csv`
- `study/control_summary.csv`
- `study/data_and_semantics_receipt.json`

A bounded private text mirror may expose only reviewed summaries under the existing public-controller → standard-executor → verified-private-mirror governance. Large row-level data remain private.

`RESULTS.json` must explicitly include:

- `relationship_verdict`;
- every individual frozen verdict check;
- `risk_probability_semantics = recovery_probability_not_high_risk_probability`;
- `reliability_used_as_market_state = false`;
- `entry_rule_changed = false`;
- `exit_rule_changed = false`;
- `position_sizing_changed = false`;
- `parameter_search_performed = false`;
- `threshold_search_performed = false`;
- `state_machine_authority = false`;
- `production_authority = false`;
- `fresh_oos_claimed = false`.

## 11. Prohibited actions

This study may not:

- interpret reliability `LOW/MID/HIGH` as volatility or market risk;
- invent or rename `recovery_probability` as a high-risk probability;
- impute probability outside eligible Risk Tool cohort rows;
- modify any OLS entry or exit formula;
- rescue D2 or Phase B re-entry candidates;
- tune PE, volatility, reversal, probability, or state thresholds on observed OLS losses;
- choose only frozen-midline or only 2024 Q4;
- define high volatility as automatically unsuitable for OLS;
- discard high-volatility trend periods from the analysis;
- launch a state machine, filter, cooldown, sizing overlay, or trading intervention before this diagnostic verdict;
- claim any 2020–2025 observation is fresh OOS.

## 12. Execution gate

Execution wiring may be added only after this preregistration is present on the current public control-plane branch. The broker must pin every private source/release/blob and fail closed on identity drift. The standard research run must remain `workflow_dispatch` on `cloud-workspace-v1`; no push/PR substitute may execute private research.
