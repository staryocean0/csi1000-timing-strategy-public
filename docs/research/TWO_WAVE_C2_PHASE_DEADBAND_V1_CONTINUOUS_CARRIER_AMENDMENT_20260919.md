# Two-Wave C2 phase deadband V1 — continuous carrier amendment

Issue #432. This amendment is frozen before the corrected deadband/persistence run.

## Why amendment is required

The first implementation attempt used the scale-specific-continuity graph hierarchy tail slope:

`tail_slope(S1) - tail_slope(S2)`.

That representation is causal but event-driven and piecewise constant between structural node confirmations.

A post-implementation audit showed that the earlier statement "125 one-native-bar C2 sign runs" was incorrect: those were one **update-event** runs, not one native-5m-bar runs. When expanded to native time, the graph-tail representation has long constant-slope segments.

Therefore it is not a valid carrier for studying native-bar anti-chatter deadbands or +8-bar phase persistence.

The local graph-tail optimization result is classified:

`INVALID_CARRIER_FOR_NATIVE_BAR_ANTICHATTER`

It is not submitted as a scientific result and is not used to choose the replacement carrier.

## Replacement continuous C2 proxy

Use an already-existing causal continuous slow component:

- family: Laplace IIR band-pass
- period: `P320`
- Q: `1.0`
- input: native 5m log close
- warmup: `3*P = 960` native bars

The component is computed by the same causal biquad convention already used elsewhere in the project:

- anchor high-pass/band-pass input to the first log-close observation;
- recursive biquad with no future sample;
- no zero-phase filtering;
- no backward pass.

## Why P320

This period is selected structurally, before deadband or persistence outcomes.

Frozen graphical Two-Wave C2 evidence:

- T0 ≈ 21 native 5m bars;
- median T2/T0 ≈ 13.60;
- implied median C2 physical period ≈ 286 bars;
- graphical C2 interquartile physical range is approximately 189-395 bars.

The project already has frozen slow-period candidates:

`{320,400,512,640,800,1024}`.

P320 is the nearest pre-existing candidate to the graphical C2 median and lies inside its empirical interquartile range.

No persistence outcome, PnL, return target, or chatter metric is used to select P320.

## Continuous slope and normalization

Let `C2_cont(t)` be the causal P320/Q1 component.

Native-bar slope:

`s(t) = C2_cont(t) - C2_cont(t-1)`.

Causal scale:

`RMS320(t) = sqrt(mean(s^2 over trailing 320 bars))`

with minimum 160 observations.

Normalized slope:

`z(t) = s(t) / RMS320(t)`.

If component warmup or RMS support is unavailable, phase is UNRESOLVED.

## Deadband protocol retained

All previously frozen deadband rules remain unchanged:

- states UP / RANGE / DOWN;
- mandatory RANGE buffer between directional states;
- exit grid 0.0..1.0 by 0.1;
- enter grid 0.1..3.0 by 0.1;
- 0 <= exit <= enter;
- anti-chatter reference boundaries 4 and 8 native bars;
- structural feasibility and lexicographic selection;
- annual parameter-dispersion gate;
- conditional-deadband contingency;
- +8 endpoint / continuous / entry-event persistence.

Only the carrier and slope normalization are amended.

## Structural sanity requirement

Before optimization, report on the corrected carrier:

- resolved native-bar count;
- raw sign-run count;
- sub-4-bar raw directional run count;
- median raw sign-run length;
- slope-z quantiles.

The corrected carrier must exhibit native-bar variability; otherwise V1 is stopped as `NO_NATIVE_BAR_ANTICHATTER_PROBLEM`.

## Authority

No primary-state relabeling, signal, strategy, trade, routing, paper/live, or production authority.
