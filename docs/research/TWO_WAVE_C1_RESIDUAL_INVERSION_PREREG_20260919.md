# C1 residual inversion audit — preregistration

Issue #554. Parent #552 / #549 / #507 / #493 / #483 / #450.

## Hypothesis

The retrospective dense C1 bandpass residual slope sign is systematically approximated by the negative of the currently visible causal S0/base skeleton leg direction.

## Discovery contamination control

The inversion clue was discovered on 2018–2020 T0 signal bars.

Primary validation universe therefore excludes **all** period-21 T0 signal bars.

Primary universe:

- every native 5m bar inside the frozen dense C1=S0-S1 oracle support;
- target slope sign nonzero;
- causal state resolvable;
- bar is not a T0 signal bar.

Secondary outputs may report all bars and T0-signal bars separately, but only the non-signal universe controls the verdict.

## Causal proxy

At bar k:

- use `_prepare_asof(stage1)` / `causal_state` on the first continuity stage;
- causal skeleton leg sign = +1 for UP, -1 for DOWN;
- inversion proxy = negative causal skeleton leg sign.

Also record:

- latest completed base-wave g sign;
- latest confirmed S0-segment slope sign.

Report whether these three causal skeleton signs are pointwise identical in the primary universe.

## Target

`target = sign(dC1_retrospective(k))` for dense C1=S0-S1.

Target is evaluation-only.

## Metrics

For both original causal skeleton sign and inverted sign:

- coverage
- balanced accuracy
- ordinary accuracy
- UP recall
- DOWN recall
- metrics by year 2015–2020.

## Structural inversion gate

`C1_RESIDUAL_INVERSION_SUPPORTED` iff on the primary non-T0-signal universe:

1. coverage >=95%;
2. inverted pooled balanced accuracy >=0.55;
3. inverted UP recall >=0.52;
4. inverted DOWN recall >=0.52;
5. inverted balanced accuracy >=0.52 in at least 5 of 6 years;
6. inverted pooled balanced accuracy exceeds the un-inverted causal leg by >=0.10.

Otherwise:

`C1_RESIDUAL_INVERSION_NOT_SUPPORTED`.

## Boundary

No T0 side, T0 PnL, compression score, future-turn label or routing outcome is used in the primary validation.

This is structural development evidence only.