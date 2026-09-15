# Two-Wave v0.8.0 — Backward Same-Scale A-Channel semantic reboot

Status: preregistered public research design candidate. Not current private authority. No trade or production authority.

## 1. Why this is a new line

This protocol does **not** rewrite or erase the historical Two-Wave v0.4–v0.7.8 chain. The historical machine authority remains read-only evidence with `morphology_acceptance=false` and no installed direction winner. The OLS/trend-regime family is out of scope and remains Layer3.

v0.8.0 restarts the Layer2 morphology question from a narrower semantic statement supplied by the user:

1. one wave has a temporal **level** defined primarily by the total bar count of one completed up+down cycle;
2. two waves may be compared only when they are of approximately the same temporal level;
3. recognition is performed **from the current confirmed wave backward into the past**, never by taking an old wave and looking forward for what happened next;
4. one wave alone does not establish a market direction; two consecutive same-scale waves must agree in direction and sufficiently agree in slope;
5. for A-phase `low → high → low`, the **lower boundary is authoritative**; the upper channel is a parallel translation of that lower boundary, not an independently fitted regression line;
6. amplitude mismatch is initially diagnostic only. It must not silently veto a pair until a later preregistered experiment proves that such a gate is needed.

## 2. Scope and non-scope

Primary object: Layer2 CSI1000 morphology classifier.

Primary view: existing DataHub-provided `5m_offset_0` view for `000852.SH`; no local resampling.

Primary phase in v0.8.0: **A-phase only**, `low → high → low`.

Output universe, when all gates are eventually satisfied: `Range`, `UpTrend`, `DownTrend`, `Uncertain`.

Explicit non-scope:

- no position, buy/sell point, PnL, cost model, execution route, or production authority;
- no OLS trend-regime family;
- no B-phase (`high → low → high`) authority in v0.8.0;
- no result-driven retuning of historical v0.7.x failures;
- no claim of fresh OOS: previously consumed dates remain consumed.

## 3. Causal A-wave definition

Let confirmed pivot occurrence bars be indexed by integer bar number. An A-wave is

`W = (L0, H0, L1)`

with occurrence bars

`t0 < tH < t1`,

where `L0` and `L1` are low pivots and `H0` is the intervening high pivot.

The wave duration / temporal level statistic is

`d(W) = t1 - t0` bars.

This is deliberately the **whole completed cycle duration**: rising-leg bars plus falling-leg bars. v0.8.0 does not require the two internal legs to have similar duration before the wave can possess a level.

The terminal low `L1` is not usable at its occurrence time. `W` becomes observable only when `L1` is causally confirmed by later information. The publication time of any state using `W` is therefore the terminal-low confirmation time, not `t1`.

Appending future bars must never alter the identity or published classification of an already published v0.8.0 record.

## 4. Same-scale relation

For two completed waves `Wa` and `Wb`, define the symmetric duration ratio

`R_d(Wa, Wb) = max(d(Wa), d(Wb)) / min(d(Wa), d(Wb))`.

They are same-scale under tolerance `rho` iff

`R_d <= rho`.

Equivalently, if the current wave has duration `N` bars, an earlier wave is in its temporal scale band iff

`ceil(N / rho) <= d(previous) <= floor(rho * N)`.

This one formula must determine the upper/lower bound for every nominal level; v0.8.0 forbids hand-writing unrelated bounds for N=5, N=10, N=20, etc.

### 4.1 Frozen diagnostic tolerance family

The first diagnostic evaluates exactly these candidates:

- `rho = 1.25`
- `rho = 4/3`
- `rho = sqrt(2)`
- `rho = 1.50`

Historical `rho = 2.00` is retained **only as a legacy control** because v0.4 allowed two-fold duration mismatch. It cannot become the v0.8 winner without a new preregistration.

Illustrative integer bands:

| current N | rho=1.25 | rho=4/3 | rho=sqrt(2) | rho=1.50 |
|---:|---:|---:|---:|---:|
| 5 | 4–6 | 4–6 | 4–7 | 4–7 |
| 10 | 8–12 | 8–13 | 8–14 | 7–15 |
| 20 | 16–25 | 15–26 | 15–28 | 14–30 |

This table is descriptive; the experiment must determine whether any candidate band is structurally credible.

## 5. Current-first backward predecessor semantics

At each `as_of` time:

1. identify the latest causally confirmed A-wave `W0` using only information available by `as_of`;
2. take `d(W0)` as the anchor level for that decision;
3. search **backward** through earlier completed A-wave candidates;
4. the predecessor candidate is the nearest earlier A-wave satisfying the tested same-scale relation;
5. the scan may pass over out-of-scale micro/macro candidates, but it may not skip an eligible same-scale predecessor to choose an older, more convenient match;
6. no bar after `as_of` and no future label/outcome may affect predecessor selection.

Two notions are reported separately:

- `shared_anchor_strict`: predecessor terminal low is exactly the current wave starting low, yielding canonical five-pivot form `L0-H0-L1-H1-L2`;
- `same_scale_ledger_nearest`: nearest earlier same-scale A-wave even when raw smaller-scale structures intervene.

v0.8.0 Phase-1 does **not** silently equate these notions. Their coverage and disagreement are an explicit diagnostic. Direction authority is not granted until this ambiguity is adjudicated.

## 6. A-channel geometry: bottom line first

Pivot **times** come from the frozen causal pivot mechanism under study. Geometry uses native bar prices at those pivot bars for the A-channel diagnostic:

- bottom anchors: native `low` at `L0` and `L1`;
- top anchor: native `high` at `H0`.

Work in log price for scale invariance. Define the lower boundary

`b_W(t) = log(L0) + ((t - t0)/(t1 - t0)) * (log(L1) - log(L0))`.

At the high-pivot time, define channel height

`h_W = log(H0) - b_W(tH)`.

A valid A-channel requires `h_W > 0`.

The upper boundary is **not separately fitted**. It is the translated line

`u_W(t) = b_W(t) + h_W`.

Thus lower and upper boundaries have exactly the same slope by construction, matching the A-phase semantic that the lower line is authoritative.

Record two slope measures:

- raw log slope per bar: `m_W = (log(L1) - log(L0)) / d(W)`;
- channel-normalized migration: `g_W = (log(L1) - log(L0)) / h_W`.

`m_W` preserves literal time slope; `g_W` expresses bottom migration in units of channel height and is the primary scale-free semantic slope candidate.

## 7. Two-wave direction is consensus, never a one-wave label

A single A-wave may have an internal descriptor, but it must not publish `UpTrend`, `DownTrend`, or `Range` as the market state.

The first direction diagnostic freezes these candidate flatness thresholds for `g_W`:

`tau ∈ {0.05, 0.10, 0.15, 0.20}`.

Internal wave descriptor under `tau`:

- `UP` if `g_W > tau`;
- `DOWN` if `g_W < -tau`;
- `RANGE` if `|g_W| <= tau`;
- invalid geometry => `UNRESOLVED`.

For two trend waves with the same sign, define normalized slope-magnitude ratio

`R_g = max(|g_prev|, |g_cur|) / min(|g_prev|, |g_cur|)`.

Frozen candidate slope-consistency limits:

`kappa ∈ {1.25, 1.50, 2.00}`.

Pair state under `(rho, tau, kappa)`:

- not same-scale => no state for this pair;
- both `RANGE` => `Range`;
- both `UP` and `R_g <= kappa` => `UpTrend`;
- both `DOWN` and `R_g <= kappa` => `DownTrend`;
- otherwise => `Uncertain`.

No pair may become decisive from one member alone.

## 8. Amplitude and path shape are diagnostic first

Channel-height ratio

`R_h = max(h_prev, h_cur) / min(h_prev, h_cur)`

is recorded but is **not** a v0.8.0 qualification gate.

To study whether the temporal-level relation corresponds to visually similar morphology without using future returns, normalize each wave path by its own bottom channel:

`z_W(t) = (log(C_t) - b_W(t)) / h_W`,

then resample the completed path onto a fixed 21-point normalized-time grid `s ∈ [0,1]` using only bars between `t0` and `t1`.

Report RMS path distance between the current and predecessor waves. This metric is descriptive and is used to see whether tighter/wider duration bands separate same-shape from cross-scale pairs. It is not a trading objective.

## 9. Validation chain

### V0800-A — synthetic semantic invariants

Must prove by deterministic unit tests:

- scale-band formula for N=5/10/20 and all frozen `rho`;
- A-channel upper boundary is an exact parallel translation of the lower boundary;
- no one-wave market-state publication;
- predecessor selection is backward-only;
- appending future bars cannot change an already published pair identity/classification;
- invalid/nonpositive channel height fails closed;
- legacy `rho=2` is control-only.

### V0800-B — duration/scale-band map

On already-consumed CSI1000 5m history, for each frozen `rho` report at minimum:

- current/predecessor duration distributions;
- support count and support fraction;
- counts stratified by current duration around 5, 10, and 20 bars;
- exact shared-anchor fraction;
- fraction requiring same-scale-ledger backward skip over out-of-scale candidates;
- duration-ratio distribution;
- channel-height ratio distribution;
- normalized 21-point path-distance median / p75 / p90;
- year-by-year stability.

No return, PnL, future horizon, or trading label may enter this experiment.

There is **no automatic rho winner** merely from maximum coverage. A later protocol may nominate a tolerance only if one candidate has a defensible coverage/shape/stability tradeoff that is not created by outcome information.

### V0800-C — causal prefix replay

Replay bar prefixes and require zero future-reference violations, zero predecessor-after-current violations, and immutable previously published records.

### V0800-D — two-wave direction grid diagnostic

Evaluate the frozen `(rho, tau, kappa)` grid only after B/C pass. Report decisive coverage, `Range/UpTrend/DownTrend/Uncertain` mix, slope-consistency distribution, year stability, and agreement/disagreement with historical D1 **as a diagnostic only**. Historical D1 is not the target label.

### V0800-E — visual audit pack

Produce a private stratified review pack containing representative windows from each state and key disagreement families. The plot must show:

- pivot times;
- current wave highlighted;
- predecessor selected strictly by backward search;
- bottom authoritative lines;
- translated top channel;
- durations and scale ratio;
- normalized slopes and final pair state.

Human visual review is morphology QA only and does not create trading authority.

## 10. Data-role discipline

All historical dates already consumed by prior Two-Wave work remain consumed. v0.8.0 is a semantic-development restart, not a reset of OOS status.

The first diagnostic should use the existing CSI1000 DataHub 5m view and may partition already-consumed years for temporal stability. 2026 must not be opened merely to rescue a weak parameter family.

## 11. Authority transition rule

Until a later adjudication explicitly says otherwise:

- historical v0.7.8 remains historical read-only authority/evidence;
- v0.8.0 is a Development candidate line;
- `morphology_acceptance=false` remains in force;
- no direction winner is installed;
- no trade/production authority exists.

The purpose of v0.8.0 is narrower: determine whether a **current-first, backward-looking, same-temporal-level, bottom-channel two-wave definition** is coherent enough to revive the Layer2 morphology tool before any downstream strategy work is considered.
