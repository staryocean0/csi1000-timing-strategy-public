# Single-frequency local compression × directional state-exit hazard — preregistration Amendment A

Issue #624.

Date: 2026-09-20.

Status: `FROZEN_BEFORE_OUTCOME_EXECUTION`

Parent preregistration: `TWO_WAVE_LOCAL_STATE_EXIT_COMPRESSION_PREREG_20260920.*`.

Architecture authority: `TWO_WAVE_STRATEGY_EVOLUTION_HISTORY_20260920.md`.

## Why this amendment is required

The original preregistration defined primary state exit as any future change of the accepted five-state wrapper label, including:

- `CURRENT_UP/DOWN → LOW_AMPLITUDE_VETO`;
- `CURRENT_UP/DOWN → FINER_SCALE_OUT_OF_BAND`.

That target is not sufficiently independent of the proposed compression predictor.

The compression family contains current local range / realized-volatility / path-efficiency information, while `LOW_AMPLITUDE_VETO` is itself defined by a frozen local-amplitude gate. A positive result could therefore partly become:

> local compression predicts a future label that is itself mechanically triggered by low local amplitude.

No #624 outcome has been executed or inspected before this amendment.

The scientific target must instead be the **termination of the underlying directional carrier**, independent of LOW/FINER quality gates.

## Frozen directional carrier

Reuse the accepted current-band recognizer V1 unchanged.

For each knowledge bar `k`, using the same 64 native 5m closes ending at `k`, compute the already-frozen recognizer direction score:

`D(k) = direction_score(close[k-63:k+1], FROZEN_WEIGHTS)`.

Do not use amplitude or FINER gates to define this carrier.

Frozen direction threshold remains exactly `±0.20`:

- `D(k) > +0.20 → DIR_UP`;
- `D(k) < -0.20 → DIR_DOWN`;
- otherwise `DIR_RANGE`.

No weight, threshold, lookback or preprocessing is refit.

## Eligible population

Eligibility remains as originally preregistered:

- accepted delayed five-state wrapper label at knowledge bar `k` must be `CURRENT_UP` or `CURRENT_DOWN`.

Require as a fail-closed invariant:

- `CURRENT_UP → DIR_UP`;
- `CURRENT_DOWN → DIR_DOWN`.

If this identity fails for any eligible row, execution stops.

Thus the amendment does not broaden the original decision population.

## Amended primary target

Let `dir0` be the frozen directional carrier at eligible knowledge bar `k`.

Primary:

`STRUCTURAL_EXIT_NEXT8 = 1`

iff any frozen directional-carrier state in `k+1 ... k+8` differs from `dir0`.

Therefore:

- DIR_UP → DIR_RANGE counts as exit;
- DIR_UP → DIR_DOWN counts as exit;
- DIR_DOWN → DIR_RANGE counts as exit;
- DIR_DOWN → DIR_UP counts as exit.

The destination is not predicted and does not enter score construction.

Secondary structural target:

- `STRUCTURAL_EXIT_NEXT16`, defined analogously through `k+16`.

This is the only target family used by the support/information gate.

## Five-state gate transitions are diagnostics only

Retain the original five-state wrapper path for diagnostics:

- exact-label exit within +8/+16;
- first exact-label exit destination;
- LOW-first incidence;
- FINER-first incidence;
- opposite-direction face-slap.

But no five-state exact-label exit, LOW transition or FINER transition may satisfy the primary support/information gate.

This preserves the useful trading interpretation that quality gates matter while preventing a predictor-target definitional loop.

## Directional age amendment

Because the primary target is now directional-carrier survival, the primary `state_age` confounder is also defined on that same frozen carrier:

> number of consecutive knowledge bars ending at `k` with the same `DIR_UP` or `DIR_DOWN` carrier state.

The frozen age bins remain unchanged:

- 1–4;
- 5–8;
- 9–16;
- 17–32;
- 33+.

Exact five-state label age may be reported descriptively but is not the age-standardization variable.

## Predictor, scoring and gates unchanged except target names

All other preregistered constraints remain unchanged:

- local-only `abs_ret_8 / range_8 / rv_8 / efficiency_8`;
- prior-year reverse empirical percentiles;
- equal weights;
- prior-only B1..B5;
- test years 2018/2019/2020;
- 20-trading-day block bootstrap;
- 5,000 reps, seed 20260920;
- eight `known_index mod 8` overlap cohorts;
- support thresholds;
- +5pp pooled practical gate;
- +3pp UP / DOWN / age-standardized gates;
- Spearman >=0.70;
- ROC AUC >=0.55;
- all-three-year B5>B1;
- no PnL / parent context / other-frequency future input.

Every reference in the original hard gate to `EXIT_NEXT8` now means `STRUCTURAL_EXIT_NEXT8`.

Every reference to `EXIT_NEXT16` now means `STRUCTURAL_EXIT_NEXT16`.

## Interpretation boundary

A positive result would establish only:

> the target frequency's own local compression/exhaustion contains causal information about whether its already-observable directional carrier will cease to persist soon.

It still would not establish:

- a profitable exit policy;
- a B5 hard exit;
- next-direction prediction;
- cross-scale invariance;
- removal of current cross-frequency context;
- signal/router/trade/paper/live/production authority.

Economic intervention remains a separate future preregistration.
