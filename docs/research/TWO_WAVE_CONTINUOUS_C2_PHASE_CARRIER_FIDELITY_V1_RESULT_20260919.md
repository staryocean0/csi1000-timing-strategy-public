# Two-Wave continuous C2 phase carrier fidelity V1 — result

Issue #438.

## Final verdict

`NO_CONTINUOUS_C2_CARRIER_ACCEPTED`

The authoritative object remains the dense graphical Two-Wave second low-frequency component:

`C2 = S1 - S2`

from the accepted scale-specific-continuity hierarchy.

This study tested whether a causal per-native-5m Laplace-IIR component could serve as a faithful observation carrier for that graphical C2.

No persistence, return, PnL, route or trade outcome was used in carrier selection.

## Frozen graphical reference

- common retrospective S1/S2 support: 69,615 native 5m bars
- completed continuity-C2 waves: 170
- graphical duration anchors used to preselect candidate periods:
  - Q25 ≈ 254 bars
  - median ≈ 377 bars
  - Q75 ≈ 534.25 bars

Frozen candidates:

- P256 / Q1
- P384 / Q1
- P512 / Q1

No other period was searched.

## P256

Passed:

- coverage: 99.28%
- causal support: 69,345 bars
- turn median absolute error: 14.5 bars
- turn Q75 absolute error: 30 bars
- retrospective DOWN-leg agreement: 63.20%
- prefix causality: passed at 10k / 30k / 50k

Failed:

- zero-lag level correlation: **0.152** < 0.55
- retrospective overall leg agreement: **59.69%** < 65%
- retrospective UP-leg agreement: **56.91%** < 60%
- causal as-of leg agreement: **40.96%** < 65%
- crossings per graphical C2 wave:
  - median **12** > 2
  - Q90 **28** > 4

Verdict: `FIDELITY_FAIL`.

## P384

Passed:

- coverage: 98.73%
- causal support: 68,961 bars
- retrospective UP agreement: 61.54%
- retrospective DOWN agreement: 67.22%
- turn median error: 22 bars
- turn Q75 error: 41 bars
- prefix causality: passed

Failed:

- zero-lag level correlation: **0.216** < 0.55
- retrospective overall leg agreement: **64.05%** < 65%
- causal as-of leg agreement: **40.70%** < 65%
- crossings per graphical C2 wave:
  - median **9** > 2
  - Q90 **22.3** > 4

Verdict: `FIDELITY_FAIL`.

## P512

P512 is the strongest of the three candidates on retrospective directional agreement, but it still fails the frozen fidelity gate.

Passed:

- coverage: 98.18%
- causal support: 68,577 bars
- retrospective overall leg agreement: 66.02%
- retrospective UP agreement: 64.04%
- retrospective DOWN agreement: 68.50%
- turn median error: 28 bars
- turn Q75 error: 50 bars
- prefix causality: passed

Failed:

- zero-lag level correlation: **0.248** < 0.55
- causal as-of leg agreement: **44.63%** < 65%
- crossings per graphical C2 wave:
  - median **8** > 2
  - Q90 **20** > 4

Verdict: `FIDELITY_FAIL`.

## Why no candidate is accepted

The negative result is not caused by causality or data coverage.

All three candidates:

- are causal under prefix replay;
- have very high bar coverage;
- have adequate comparison support;
- have acceptable median/Q75 turn timing.

The problem is morphological fidelity.

The IIR candidates:

1. correlate only weakly with the graphical C2 level;
2. disagree strongly with the causal graphical C2 leg;
3. generate far too many slope crossings inside one graphical C2 wave.

In other words, they oscillate substantially faster than the graphical second low-frequency object they were intended to observe.

Therefore using any of them as the C2 phase carrier would change the research object rather than merely observe it.

## Relation to the earlier P320 proposal

An earlier amendment proposed P320/Q1 as a continuous replacement carrier before a formal fidelity gate existed.

That proposal does not have authority after this study.

P320 is not accepted as C2 merely because its nominal period is near the graphical C2 median.

The prior accidental P320-based deadband/persistence run remains quarantined and must not be used scientifically.

## Relation to dense retrospective C2 V1.2

The dense retrospective graphical C2 result remains valid as a morphology oracle.

It established, independently of this carrier study:

- stable global structural deadband:
  - exit = 0.00
  - enter = 0.01
  - lower-boundary-limited
- no observed year/condition-specific threshold requirement
- very high +8 persistence for newly entered UP/DOWN phases
- very low +8 persistence for newly entered RANGE

However, those are retrospective morphology results.

This fidelity study shows that none of P256/P384/P512 currently earns the right to carry that phase causally at every native 5m bar.

## Next research gate

The next causal step must be one of:

1. a new preregistered continuous carrier family with a materially different representation; or
2. a delayed recognizer trained/evaluated directly against the frozen dense retrospective C2 phase oracle.

No failed IIR candidate may be retuned using the already visible phase-persistence result.

## Evidence

Fixed source:

- rows: 70,114
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

Exact implementation SHA256:

`23527c81b064b4e6621ccc0c11ca75734ec7ecb80dd3d11df717c2c8e114cae6`

Execution result SHA256:

`4a1d59a91abe50416a23b91dbe2f6043bcd49ecae7aeaf0d97d89a2036f1318c`

## Governance

No primary-state relabeling, signal, strategy selection, routing, trade, PnL-selection, paper/live or production authority.
