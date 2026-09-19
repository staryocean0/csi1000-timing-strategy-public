# Two-Wave continuous C2 phase carrier fidelity V1 — preregistration

Issue #438.

## 1. Authority and purpose

The graphical hierarchy remains authoritative:

`C2 = S1 - S2`

from scale-specific continuity.

The purpose is only to find a causal per-native-5m **observation carrier** whose continuously updated component is faithful enough to the graphical C2 to support later phase-deadband research.

A proxy does not redefine C2.

No persistence, return, PnL, route or trade outcome is used in carrier selection.

## 2. Frozen graphical scale evidence

Previously established continuity C2 complete-wave durations:

- n = 170
- Q25 = 254 bars
- median = 377 bars
- Q75 = 534.25 bars

Candidate periods are fixed by rounding these three pre-existing graphical duration anchors to nearby 64-bar multiples:

- P256
- P384
- P512

No other period may be introduced in V1.

## 3. Proxy family

Each candidate is a causal Laplace-IIR biquad bandpass:

- period P in {256,384,512}
- Q = 1.0
- input = log close
- warmup = 3P native bars

Q=1 is inherited from the existing causal Laplace-IIR research family and is not tuned in this study.

The component value at k may use only source bars <=k.

Phase slope is the first difference of the component.

## 4. Retrospective graphical level reference

Build the complete scale-specific continuity hierarchy without modifying the frozen base ledger.

Let:

- S1 nodes = continuity stage-2 input stream
- S2 nodes = continuity stage-3 input stream

Using the fully completed morphology only for retrospective fidelity:

- linearly interpolate log(S1 node price) on occurrence-bar coordinates;
- linearly interpolate log(S2 node price) on occurrence-bar coordinates;
- common support is the overlap of the first/last S1 and S2 occurrence bars;
- reference component:
  `C2_ref(t)=S1_interp(t)-S2_interp(t)`.

This retrospective curve is never claimed to be a live signal.

## 5. Retrospective graphical leg reference

Use all 170 completed continuity-C2 waves.

For each low-high-low wave:

- start_low -> high = graphical UP leg
- high -> end_low = graphical DOWN leg

Shared anchors are assigned deterministically left-closed/right-open to avoid double labels.

Compare sign(proxy slope) with graphical leg direction on covered bars after candidate warmup.

Report:

- overall agreement
- UP-leg agreement
- DOWN-leg agreement
- support bars

## 6. Causal as-of graphical leg reference

For continuity C2, at each knowledge bar k use only then-known:

- confirmed C2 pivot
- completed C2 wave
- confirmed continuity node

The causal leg is:

- UP after latest confirmed low pivot
- DOWN after latest confirmed high pivot

Only RESOLVED causal graphical-C2 bars enter this comparison.

Compare sign(proxy slope(k)) with the causal graphical leg at the same k.

No future graphical pivot may be backfilled.

## 7. Turn-timing reference

Use non-left-censored continuity-C2 pivots.

Matching proxy slope crossings:

- graphical high pivot -> positive-to-negative proxy-slope crossing
- graphical low pivot -> negative-to-positive proxy-slope crossing

For each graphical pivot, take the nearest matching crossing in occurrence time.

Report absolute timing error in native bars.

Frozen timing gates:

- median absolute error <= 57 bars
- Q75 absolute error <= 114 bars

These are approximately 15% and 30% of the pre-existing graphical C2 median duration 377.

## 8. Excess-turn audit

For each complete graphical C2 wave, count proxy-slope sign crossings strictly inside the wave span.

A low-high-low wave has one principal interior turn.

Frozen anti-oversegmentation gates:

- median crossings per wave <= 2
- Q90 crossings per wave <= 4

## 9. Level fidelity

On common retrospective C2 support after candidate warmup:

- center both proxy component and C2_ref;
- standardize each by its own standard deviation;
- compute zero-lag Pearson correlation.

Gate:

- correlation >= 0.55

Also report the best lagged correlation for lags -128..+128 and its lag, but it does not replace the zero-lag gate.

## 10. Direction fidelity gates

Retrospective completed-wave leg:

- overall sign agreement >= 0.65
- UP agreement >= 0.60
- DOWN agreement >= 0.60

Causal as-of graphical leg:

- sign agreement >= 0.65

## 11. Coverage and causality gates

For each candidate:

- retrospective common-support coverage after warmup >= 0.90
- causal graphical comparison support >= 5,000 bars
- prefix replay must be numerically identical (atol 1e-12) at cuts 10,000 / 30,000 / 50,000

Any causality failure rejects the candidate.

## 12. Candidate verdict

A candidate is `FIDELITY_PASS` only if every gate in sections 7-11 passes.

If zero candidates pass:

`NO_CONTINUOUS_C2_CARRIER_ACCEPTED`

and deadband/persistence work remains blocked.

If one or more pass, select lexicographically:

1. highest zero-lag C2 level correlation
2. highest causal as-of leg agreement
3. lowest median turn absolute error
4. smallest absolute period distance from graphical median 377

Selection uses no persistence outcome.

## 13. After a carrier passes

The selected carrier must be frozen in a separate checkpoint before any new RANGE deadband optimization or +8 persistence calculation.

No carrier/deadband joint tuning is allowed.

## 14. Governance

Development evidence is previously consumed, not fresh OOS.

No signal, strategy selection, routing, trade, paper/live or production authority.
