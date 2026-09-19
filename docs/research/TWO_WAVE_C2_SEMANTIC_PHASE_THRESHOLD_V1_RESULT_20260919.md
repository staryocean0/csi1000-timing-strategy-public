# Two-Wave C2 semantic phase threshold V1 — result

Issue #444.

## Final verdict

`BASE_SLOPE_ALONE_INSUFFICIENT_FOR_C2_SEMANTIC_PHASE`

The requested calibration was performed in the correct causal-independent order:

1. completed large-cycle C2 waves were labeled UP / RANGE / DOWN from C2's own large-scale geometry;
2. only afterward was the current-band low-point-line normalized migration `g_base` exposed;
3. asymmetric `t_down / t_up` thresholds were fit to recover the large-cycle C2 oracle;
4. threshold uncertainty was measured by completed-C2-wave cluster bootstrap.

No persistence, PnL, future-return magnitude, route or trade outcome entered threshold selection.

## Independent large-cycle oracle

Continuity C2 complete waves:

- C2_UP: 81
- C2_DOWN: 68
- C2_RANGE: 21

Large-cycle labels use C2's own normalized low-line migration:

- RANGE if `|g_C2| <= 0.20`
- UP if `g_C2 > 0.20`
- DOWN if `g_C2 < -0.20`

The current-band slope `g_base` is not used to create these labels.

## Current-band waves mapped into C2

Eligible fully-contained base waves:

- inside C2_UP: 1,180
- inside C2_DOWN: 990
- inside C2_RANGE: 315
- total: 2,485

All 170 completed C2 waves contribute at least one contained base wave.

## What the distributions show

The current-band low-point-line slope strongly overlaps across the three large-cycle phases.

### Inside large-cycle DOWN

- median `g_base`: about -0.11
- 25%-75%: about -0.83 to +0.61
- positive-slope share: **45.35%**

### Inside large-cycle RANGE

- median `g_base`: about +0.02
- 25%-75%: about -0.62 to +0.86
- positive-slope share: **51.43%**
- `|g_base| <= 0.20`: only **17.14%**
- `|g_base| <= 0.50`: only **39.37%**

### Inside large-cycle UP

- median `g_base`: about +0.13
- 25%-75%: about -0.48 to +0.87
- positive-slope share: **55.85%**

Therefore a genuine large-cycle RANGE contains many materially positive and negative current-band slopes, exactly as hypothesized.

Conversely, large-cycle UP and DOWN also contain many current-band waves whose slope points against the large-cycle direction.

## Best possible global one-dimensional threshold

Allow asymmetric thresholds:

- DOWN if `g_base < t_down`
- RANGE if `t_down <= g_base <= t_up`
- UP if `g_base > t_up`

Full-sample optimum under preregistered macro-balanced objective:

- `t_down = -0.3681`
- `t_up = +0.0529`

But classification quality is weak:

- DOWN recall: **40.20%**
- RANGE recall: **20.63%**
- UP recall: **53.56%**
- macro balanced accuracy: **38.13%**

Random three-class reference is 33.33%.

The preregistered acceptance requirements were:

- macro balanced accuracy >=45%
- every class recall >=40%

The RANGE recall and macro gate fail decisively.

## Threshold variance

2,000 stratified completed-C2-wave bootstrap replicates, seed 20260919.

### Lower boundary t_down

- median: **-0.503**
- 95% interval: **[-1.354, +0.606]**
- MAD: **0.375**
- normalized MAD: **0.744**
- 95% interval width: **1.960**

### Upper boundary t_up

- median: **+0.052**
- 95% interval: **[-0.757, +1.752]**
- MAD: **0.324**
- normalized MAD: **3.243**
- 95% interval width: **2.508**

Both thresholds fail every preregistered stability gate.

The intervals cross zero and span ranges far wider than the proposed RANGE interval itself.

Therefore the full-sample average thresholds do not have stable semantic meaning.

## Sample-support gate

The large-cycle RANGE oracle also has limited independent support:

- only 21 completed C2_RANGE waves versus the preregistered minimum 30;
- only 315 contained base waves versus the preregistered minimum 500.

This is an additional reason not to freeze a global threshold.

## Predeclared condition diagnostics

Three condition families were checked without changing the V1 verdict:

- C2 amplitude tertile
- C2 duration tertile
- base-wave EARLY / MIDDLE / LATE position inside C2

None reaches the preregistered 45% macro-balanced threshold.

Best observed cells are only about 43.4% macro balanced accuracy.

Examples:

- high C2-amplitude tertile: about **43.36%**
- late position inside C2: about **43.31%**
- middle position: about **42.05%**

The conditions change the fitted thresholds substantially, which confirms contextual dependence, but no tested single condition produces sufficiently clean three-phase separation.

These diagnostics are not promoted to a conditional production rule.

## Scientific conclusion

The data supports the user's structural hypothesis:

> the small/current-band low-point-line slope is not supposed to be near zero whenever the large-cycle C2 is in a horizontal/range regime.

Large-cycle RANGE can contain strongly rising and falling smaller waves.

But the stronger result is:

> **large-cycle C2 semantic phase cannot be recovered reliably from current-band low-point-line slope alone.**

This is not merely a threshold-width problem.

A one-dimensional global threshold is both weakly separating and highly unstable.

Therefore no global `g_base` RANGE interval is accepted.

## What must be added next

The next model needs at least one additional piece of large-cycle context beyond the current-band slope itself.

The current V1 evidence points toward a state representation involving some combination of:

- current-band low-point-line slope `g_base`
- position within the large C2 morphology
- large-cycle amplitude / pace
- large-cycle turning / envelope geometry

A new conditional model must be separately preregistered.

The already visible persistence results may not be used to choose its thresholds.

## Delayed-following boundary

The previous dense-C2 `UP=100% / DOWN≈99.5%` +8 result is not used here and has already been formally reinterpreted.

After a semantic phase recognizer exists, the relevant delayed-following outcomes begin after the knowledge boundary:

- alive at t+8
- same phase at t+16 conditional on alive at t+8
- continuous survival from t+9 through t+16
- residual phase life after t+8
- post-t+8 decay/reversal hazard

## Evidence

Exact implementation SHA256:

`71480e4c93846a5158e42d7e64d096d2708ec0a44b974fcee40162e43107d4da`

Exact result SHA256:

`83483ffcc7076e54d316bbf89091e6e25cc4de06d8891327f3a4e32e249bd1e7`

Formal evidence:

- mapping ledger SHA256: `1735e36e92f2c4a2d53f179928fab8e31ec300dc163c9b610cf9f909013dab41`
- wave-cluster bootstrap SHA256: `451760dc36241145a564537a4d38a35980c267e95050f2490b991677689970dc`
- class distributions SHA256: `15fe79bde56293caa2e6708a0d8731ef04deddbca95b0b38c5e65737fc6100ce`
- condition diagnostics SHA256: `b778f4054362bce5d14a5d4da0465979969273a4ea80ef3c92fd421b4c725906`

## Governance

No primary five-state relabeling, signal, strategy selection, routing, trade, PnL-selection, paper/live or production authority.
