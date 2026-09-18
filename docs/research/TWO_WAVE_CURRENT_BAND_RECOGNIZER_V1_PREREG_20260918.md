# Two-Wave current-band recognizer V1 — preregistration

Issue #420. This recognizer targets the frozen V2.1 trade-oriented primary taxonomy.

## Target oracle

Frozen final-label SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

Frozen primary states:

- CURRENT_UP
- CURRENT_RANGE
- CURRENT_DOWN
- LOW_AMPLITUDE_VETO
- FINER_SCALE_OUT_OF_BAND

The recognizer does not reopen or relabel the taxonomy.

## Information boundary

For target native 5m bar `t`, the recognizer may use only:

- the 64-bar native-5m current-band path ending at `t+8`;
- native OHLC inside the frozen local amplitude window `[t-8,t+8]`;
- technical validity/support flags for DATA_INVALID handling.

It must not use:

- 128/256 context;
- parent-scale direction;
- date/year;
- challenge stratum;
- old six-bucket labels;
- old recognizer output;
- future bars after t+8;
- return, PnL or trade outcome.

## Frozen LOW gate

[
A_{local,bps}=10000(maxlog H-minlog L)
]

over `[t-8,t+8]`.

`A_local_bps < 31.03573193149245` -> LOW_AMPLITUDE_VETO.

Equality passes.

This threshold is not calibrated in the recognizer.

## Frozen FINER gate

On the 64-bar normalized log-close path:

1. inspect the last 24 raw bars;
2. require return-sign changes >= 9;
3. require median same-sign run length <= 2 bars;
4. partition all 64 bars into sixteen non-overlapping four-bar blocks;
5. compute:
   - range_ratio = range(block means) / range(raw 64);
   - residual_fraction = MSE(raw - repeated block mean) / MSE(raw - raw mean);
   - tv_ratio = TV(block means) / TV(raw 64);
   - recent_abs_drift = absolute normalized drift of last eight block means;
   - full_abs_drift = absolute normalized drift of all block means.

FINER fires when all are true:

- range_ratio < 0.55;
- residual_fraction > 0.38;
- tv_ratio < 0.35;
- recent_abs_drift < 0.25;
- full_abs_drift < 0.25.

This gate is frozen from the reference semantics and is not fitted against recognizer accuracy.

## Direction coordinate

For each phase `p in {0,1,2,3}`:

1. start at native-bar offset p;
2. form consecutive four-bar block means;
3. find recent alternating extrema on the block-mean path;
4. if a recent same-phase triple exists, compute normalized same-phase migration `g_p`;
5. otherwise use the phase-specific developing normalized drift `d_p`.

The per-phase signed coordinate is therefore `q_p = g_p` when available, otherwise `d_p`.

A fifth coordinate `q_raw` comes from the raw-close minimum-leg-4 pivot chain; if no recent complete same-phase triple exists, use its mature developing leg/drift fallback.

Coordinates are clipped to [-2, 2] only for numerical robustness.

## Allowed calibration

The final signed direction score is:

[
D = w_0 q_0+w_1 q_1+w_2 q_2+w_3 q_3+w_4 q_{raw}
]

with:

- `w_i >= 0`;
- `sum(w_i)=1`.

Only the five convex weights may be fitted.

The direction threshold remains frozen:

- D > +0.20 -> CURRENT_UP;
- |D| <= 0.20 -> CURRENT_RANGE;
- D < -0.20 -> CURRENT_DOWN.

No intercept, class-specific threshold, amplitude threshold, parent feature or generic multiclass model is allowed.

## Protected split

Salt:

`tw-current-band-rec-v1|`

Within each frozen final class, sort panel IDs by:

`SHA256(salt + panel_id)`.

For CURRENT_UP / CURRENT_RANGE / CURRENT_DOWN / LOW_AMPLITUDE_VETO:

- every fifth ranked panel is protected evaluation;
- all others are calibration.

For the rare FINER_SCALE_OUT_OF_BAND class:

- the first hash-ranked panel is protected evaluation;
- the remaining two are calibration.

Expected protected count from the frozen class totals is 78.

The protected-label file must be sealed and made unreadable before any recognizer metric is computed.

## Calibration objective

Lexicographic:

1. preserve LOW and FINER semantic gates;
2. maximize exact five-state identity on calibration;
3. maximize macro recall as tie-break;
4. prefer flatter/non-concentrated convex weights when exact identity and macro recall tie.

No outcome/PnL objective is allowed.

## Progression gate before protected evaluation

Do not consume the protected evaluation slice unless calibration satisfies all:

- LOW recall = 1.0;
- FINER recall = 1.0;
- overall exact identity >= 0.80;
- macro recall >= 0.75;
- no primary state has recall below 0.60.

If this gate fails, reject V1 without opening protected labels.

## Protected evaluation

After weights are frozen, open the protected labels once and report:

- exact identity;
- confusion matrix;
- per-state recall/precision;
- LOW and FINER exactness;
- deterministic replay.

No retuning under the same V1 identity is permitted after protected evaluation is opened.

## Wrapper boundary

The `8 × native 5m` delayed-causal retrospective-equivalent wrapper remains out of scope.

It begins only after the retrospective recognizer is accepted and frozen.

## Authority

No signal, trade, router, PnL-selection, paper/live or production authority.
