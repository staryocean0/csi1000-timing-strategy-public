# OLS D0 — Maximum-Drawdown Attribution Execution Status

Status: **D0 infrastructure ready; empirical attribution not yet claimed**.

This note is the execution companion to `NEXT_STAGE_DRAWDOWN_CONTROL.md`.  The
research target is maximum-drawdown reduction.  D0 is diagnosis only: no entry,
exit, threshold, routing, sizing, leverage, or production rule may be changed
before the baseline drawdown episodes are described.

## 1. What is already frozen

The current CSI1000 runtime contains a trading OLS lifecycle in
`runtime/src/factor_lab/market_state/ols_explosive_channel_v1.py`:

- fast authority family: W12/W24;
- executable position is the previous-bar decision (`close_t` decision,
  `open_t+1` execution semantics);
- candidate-window score already includes live OLS `fit_r2` and
  `path_efficiency`;
- native exit families include qualification reset, opposite-close variants,
  prior-extreme break and frozen OLS midline break;
- the runtime is research authority only.

The migrated 20-bar trend-regime baseline separately exposes `r_squared`,
`slope_t`, and slope.  For a fixed window, `|slope_t|` is monotone in R2, so a
static R2 floor is not assumed to be a new independent source of information.
D0 therefore focuses first on *deterioration through time* rather than tuning a
second static fit threshold.

## 2. D0 executable artifacts

Cloud branch now contains:

- `ols_drawdown_trace_adapter.py` — maps the native W12/W24 up/down carrier onto
  the currently executable side and authority window;
- `ols_drawdown_atlas.py` — computes equity, underwater episodes and the signal
  state surrounding each drawdown.

The adapter does **not** calculate strategy return.  `strategy_return` must be
supplied by the authoritative backtest/execution trace so transaction-cost and
execution conventions cannot silently drift.

For non-flat bars, D0 observes the CURRENT bar's `fit_r2`, path efficiency and
slope from the side/window currently carrying executable risk.  Flat bars have
no active R2.  R2 decline counters reset on flat or direction reversal; decline
signals may not leak across separate trades.

## 3. Minimum joined native trace contract

Required lifecycle / return fields:

- `timestamp`
- `strategy_return`
- `executable_position`
- `executable_authority_window_bars`
- `direction_conflict`
- `exit_trigger`

Required regression fields for side in `{up,down}`, window in `{12,24}`:

- `context_free_explosive_{side}_w{window}_fit_r2`
- `context_free_explosive_{side}_w{window}_path_efficiency`
- `context_free_explosive_{side}_w{window}_slope_log_per_15m`
- `context_free_explosive_{side}_w{window}_qualified`

Optional but useful:

- `close`
- `up_live_ols_midline`, `down_live_ols_midline`
- future slow/router diagnostics such as `slow_state`, `slow_fit_r2`

## 4. Atlas readout

For the worst drawdown episodes D0 records, at minimum:

- peak → drawdown start → trough → recovery;
- depth and underwater duration;
- executable direction and W12/W24 authority at start/trough;
- authority-window switches before trough;
- active R2 at start/trough, minimum/maximum and peak-to-trough collapse;
- first negative ΔR2 and first two-consecutive negative ΔR2 observations;
- their lead in bars to the drawdown trough;
- path efficiency and slope where available;
- direction-conflict and native-exit activity;
- optional slow-OLS state/fit once a router candidate exists.

## 5. Questions D0 must answer before any optimization

1. Do large drawdowns concentrate in already-low-fit trades, or do they begin
   from apparently strong fits that subsequently collapse?
2. Does R2 deterioration occur **before** the first material adverse PnL / native
   exit, or only after price reversal has already done the damage?
3. Is the useful signal absolute R2, relative drop from entry, drop from the
   trade's best R2, negative R2 slope, or persistence of negative ΔR2?
4. Do W12/W24 authority switches cluster near drawdowns?
5. Does path-efficiency deterioration add information beyond R2 deterioration?
6. Are the worst losses primarily false-trend entries, trend endings, fast
   reversals/gaps, or delayed exits from previously valid trends?

No answer is presumed in advance.

## 6. Current evidence gap

The current online public/private Git trees do not expose a committed empirical
per-bar OLS strategy-return trace that can be treated as the authoritative D0
input.  Therefore no claim is made yet that R2 deterioration explains the
historical maximum drawdown, and no R2 veto threshold is authorized.

The next executable step is deterministic: materialize or supply the joined
native trace above, run `ols_drawdown_trace_adapter.py`, then run
`ols_drawdown_atlas.py`.  The resulting atlas is the gate for D1.

## 7. D1/D2 gate

Only after D0 evidence exists may research proceed to:

- D1: low-degree-of-freedom R2 deterioration veto/exit candidates;
- D2: slow/big OLS regime router → fast/small OLS trading family;
- D3: joint drawdown-control model.

Primary acceptance metrics remain maximum drawdown, drawdown duration/recovery,
and return-to-drawdown efficiency.  Return and Sharpe are secondary and cannot
justify a materially worse drawdown profile.
