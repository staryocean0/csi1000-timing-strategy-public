# Two-Wave C2 semantic phase threshold V1 — preregistration

Issue #444.

## 1. Purpose

Infer the current-band low-point-line slope interval associated with the **independently defined large-cycle C2 phase**.

This replaces the earlier approach that chose a RANGE deadband by minimizing chatter and RANGE occupancy.

The question is:

> When the true large-cycle C2 morphology is UP / RANGE / DOWN, what current-band bottom-line normalized migration values are actually observed inside it?

## 2. Independent large-cycle oracle

Use completed C2 waves from the accepted scale-specific-continuity hierarchy.

For each completed C2 low-high-low wave compute its own large-cycle geometry:

`g_C2 = [log(end_low)-log(start_low)] / C2_channel_height`.

The already frozen large-cycle descriptor is:

- C2_RANGE if `|g_C2| <= 0.20`
- C2_UP if `g_C2 > 0.20`
- C2_DOWN if `g_C2 < -0.20`

This label is determined entirely from the C2 wave itself.

The current-band slope being calibrated is not used to create the C2 label.

## 3. Current-band slope variable

Use the existing Two-Wave base/current-band completed wave geometry.

For each base low-high-low wave:

`g_base = [log(end_low)-log(start_low)] / base_channel_height`.

This is the frozen current-band low-point-line normalized migration.

No close-OLS, raw-price long-window slope, or IIR slope may substitute for `g_base`.

## 4. Mapping base waves into C2 oracle waves

A base wave is eligible only when its full occurrence interval:

`[base_start_bar, base_end_bar]`

is entirely contained in one completed C2 wave occurrence interval:

`[C2_start_bar, C2_end_bar]`.

Base waves crossing a C2 boundary are excluded.

Each eligible row stores:

- C2 wave id
- C2 direction oracle
- C2 g
- base wave id
- base g
- base duration
- relative base-wave midpoint position inside C2 wave

No future return or PnL field enters the ledger.

## 5. One-dimensional semantic thresholds

Fit two thresholds:

- `t_down`
- `t_up`

with `t_down < t_up`.

Prediction from current-band g alone:

- DOWN if `g_base < t_down`
- RANGE if `t_down <= g_base <= t_up`
- UP if `g_base > t_up`

Thresholds are allowed to be asymmetric.

## 6. Objective

Primary objective is three-class macro balanced accuracy:

`(recall_DOWN + recall_RANGE + recall_UP) / 3`.

This prevents the largest C2 class from dominating threshold selection.

Search candidates are the midpoints between sorted unique observed `g_base` values plus outer sentinels.

Select the pair maximizing lexicographically:

1. macro balanced accuracy;
2. RANGE recall;
3. minimum absolute asymmetry `|t_up + t_down|`;
4. minimum RANGE width `t_up - t_down`.

No persistence outcome participates.

## 7. Identifiability gates

A global semantic threshold pair is considered identifiable only if:

1. each C2 oracle class has at least 30 completed C2 waves;
2. each class contributes at least 500 eligible base waves;
3. full-sample macro balanced accuracy >= 0.45;
4. RANGE recall >= 0.40;
5. UP recall >= 0.40;
6. DOWN recall >= 0.40.

These gates are intentionally above random 1/3 but do not require near-perfect separability.

If the gates fail, conclusion is:

`BASE_SLOPE_ALONE_INSUFFICIENT_FOR_C2_SEMANTIC_PHASE`.

## 8. Wave-cluster bootstrap

Resampling unit is completed C2 wave, not individual base wave.

Bootstrap:

- 2,000 replicates
- fixed RNG seed 20260919
- sample C2 waves with replacement within each C2 oracle class
- refit `t_down` and `t_up` on every replicate

Report for each threshold:

- median
- 2.5% / 97.5% percentile interval
- MAD
- normalized MAD = MAD / max(|median|, 0.1)

## 9. Threshold stability gate

Global thresholds are `STABLE_GLOBAL` only if both thresholds have:

- normalized MAD <= 0.35
- 95% interval width <= 0.75

and the full-sample performance gates pass.

Otherwise:

`HIGH_VARIANCE_OR_WEAK_SEPARATION`

and one global semantic RANGE interval is not accepted.

## 10. Predeclared condition diagnostics

Only if the global threshold fails stability or separation, report threshold fits by these predeclared conditions:

1. C2 wave amplitude tertile
2. C2 wave duration tertile
3. relative base-wave midpoint phase: EARLY / MIDDLE / LATE

These are diagnostics in V1, not automatically promoted to deployment thresholds.

A follow-up conditional model requires a separate preregistration.

## 11. Delayed persistence boundary

This study does not use the old dense-C2 +8 persistence numbers to choose thresholds.

After semantic thresholds are frozen, delayed-following research must use a causal recognizer and evaluate outcomes after the knowledge boundary:

- phase alive at t+8
- same phase at t+16 conditional on alive at t+8
- continuous survival t+9..t+16
- residual life after t+8
- post-t+8 decay/reversal hazard

## 12. Governance

No PnL, future-return magnitude, trade outcome, signal, routing, paper/live or production authority.

The current-band five-state classifier remains unchanged.
