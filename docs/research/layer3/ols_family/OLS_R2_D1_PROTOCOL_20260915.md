# OLS Layer3 D1 — Causal R² Deterioration Lead/Lag Protocol

Status: **pre-registered diagnostic only**. This protocol grants no trading, routing, sizing, leverage, or production authority.

## Frozen parent

- Instrument: CSI1000 `000852.SH`.
- Years: 2020–2025 only.
- Base cadence: frozen 5m carrier aggregated to 15m exactly as D0.
- OLS family: W12/W24 from the D0 replay; no change to entry qualification, scoring, lifecycle, exits, or next-bar execution.
- Exit families remain exactly:
  1. `qualification_reset`
  2. `first_opposite_close`
  3. `two_opposite_closes`
  4. `prior_extreme_break`
  5. `frozen_midline_break`
- Return convention: `open_t -> open_{t+1}` gross, zero-cost diagnostic only.
- D0 scientific parent: authoritative run `34962015785` and public source commit `d4f12c879c12bd63ab4092a4e57a515880e2f77e`.

## D1 question

D0 found that endpoint ΔR² can miss episodes where fit collapses and later partially recovers. D1 therefore asks only:

> Does **two consecutive causal decreases in the active authority-window fit R²** provide useful warning before drawdown troughs and before the already-frozen exit trigger, without being explained mainly by W12/W24 authority-window switching?

D1 does **not** test a new entry rule or replace any exit.

## Primary event

On 15m bar `t`, a primary deterioration event is true iff:

- executable position is non-zero on `t-2`, `t-1`, and `t`;
- position direction is identical on all three bars;
- active-authority `fit_r2` is finite on all three bars; and
- `R²_t < R²_{t-1} < R²_{t-2}`.

The event counter resets implicitly on flat exposure or direction reversal. It does **not** reset on authority-window switch; window switching is measured separately rather than hidden.

## Pre-registered sensitivity and confirmation

- **Same-window sensitivity**: the primary event also has the same `authority_window_bars` on all three event bars. This tests whether the primary result survives removal of cross-window comparisons.
- **PE confirmation**: at a primary event, `path_efficiency_t < path_efficiency_{t-2}`. A stricter descriptive field also records two consecutive PE decreases. PE is confirmation/attribution only; D1 may not choose a PE threshold or promote PE into a gate after seeing outcomes.

## Episode and lead/lag definitions

For each frozen exit family:

1. Reconstruct the same strategy trace and equity as D0.
2. Enumerate drawdown episodes with the D0 peak/start/trough/recovery convention.
3. Rank by drawdown depth and freeze the deepest 20 as the primary D1 episode cohort.
4. For each top-20 episode, search from the start of the active position segment containing drawdown onset through the episode trough.
5. Record the first primary event, first same-window primary event, and first PE-confirmed primary event.
6. For the first primary event record signed bars to:
   - drawdown onset (`start_idx - event_idx`);
   - drawdown trough (`trough_idx - event_idx`);
   - the first already-frozen `exit_trigger` in that event's active segment.

Positive lead means the warning precedes the target; zero means same bar; negative onset lead means the warning arrived after drawdown had already begun.

## Pre-registered summary

Per exit family report:

- total primary event count;
- total same-window event count;
- top-20 primary-event coverage;
- top-20 same-window coverage;
- top-20 PE-confirmed coverage;
- fraction of covered episodes warned before or at onset;
- median signed lead to onset;
- median lead to trough;
- count of episodes with an observable subsequent frozen exit trigger;
- fraction of those events strictly before the frozen exit;
- median lead to frozen exit;
- fraction of first primary events that are same-window;
- fraction of first primary events PE-confirmed;
- median same-window lead to trough;
- median PE-confirmed lead to trough.

## Frozen D1 decision rule

D1 is `SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST` only if **all** of the following hold:

1. top-20 primary-event coverage is at least 0.50 in at least 3 of 5 exit families;
2. median primary-event lead to the existing frozen exit is strictly positive in at least 3 of 5 exit families with observable exits;
3. same-window top-20 coverage is at least 0.40 in at least 3 of 5 exit families.

Otherwise D1 is `NOT_SUPPORTED_FOR_D2_EXIT_OVERLAY_TEST`.

Passing D1 authorizes only a separately pre-registered D2 experiment that tests an exit-risk overlay against unchanged baselines. It does not authorize production use, parameter search, an R² threshold, a new entry filter, position scaling, leverage, or routing.

## Explicit prohibitions

- no optimization or threshold sweep;
- no selection among R² delta lengths;
- no R² decay-slope winner search;
- no PE threshold fitting;
- no exit modification in D1;
- no router or position-size modification;
- no 2026 data;
- no claim that D1 improves PnL;
- no production authority.
