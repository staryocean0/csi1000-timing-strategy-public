# Two-Wave C2 phase deadband V1.1 — adjudication

Issue #432.

## Verdict

`GRAPHICAL_C2_DEADBAND_WIDTH_UNIDENTIFIED__CONTINUOUS_PHASE_CARRIER_REQUIRED`

The actual graphical second low-frequency object remains:

`C2 = S1 - S2`

from the accepted scale-specific-continuity hierarchy.

This adjudication does **not** replace C2 with a linear filter.

## Carrier integrity

Correct causal graphical-C2 ledger:

- rows: 69,372 / 70,114
- first known bar: 742
- last known bar: 70,113
- sign runs: 290
- sign changes: 289
- unique normalized-slope values: 667
- ledger SHA256:
  `7191f0ca6b762edff0967117112c3b6ead09ae6d7424da4ced61909ad7f3071c`

An accidental concurrent implementation used a P320/Q1 IIR proxy. That run is invalid and quarantined:

- invalid result SHA256:
  `db390e328fe9e20ec24b4acdf4e4b3398295b6394759a97120b8cd7496643bf9`
- invalidation checkpoint SHA256:
  `ba7acc2fb3eba69c669b6cbb22ad833075b8c9e9416ad919b3f8911580053da9`
- scientific use: forbidden

## Fine-grid structural result

V1.1 fine grid:

- exit: 0.00..0.20 by 0.01
- enter: 0.01..0.30 by 0.01
- enter > exit

Correct graphical-C2 global minimum-intervention candidate:

- exit = 0.00
- enter = 0.01
- stable-turn support = 289
- stable-entry support = 290
- exit-old-direction-within-4 = 1.0000
- enter-new-direction-within-8 = 0.99655
- short directional episodes = 0
- short same-direction RANGE roundtrips = 0
- RANGE occupancy = 0.5175%

All six years are feasible and all independently choose:

`exit=0.00, enter=0.01`

Therefore measured annual threshold variance is zero at the tested resolution.

## Why 0.01 is not frozen as a scientific optimum

The candidate hits the minimum positive enter threshold in the V1.1 search.

More importantly, a corrected native-bar audit shows:

- raw graphical-C2 sign runs = 290
- raw directional runs shorter than 4 native bars = 0

The earlier claim of 125 one-bar runs came from counting one **C2 update event** as one native bar. It was a clock-interpretation error.

Therefore the graphical C2 tail-slope carrier does not present native-5m chatter that can identify a nonzero deadband width.

The V1.1 selection only proves:

> forcing every direction reversal through RANGE plus an arbitrarily small positive re-entry band is enough on this sparse carrier.

It does **not** identify where a genuine horizontal-slope interval should sit.

The parameter is lower-bound limited, not condition-dependent.

## Why the +8 persistence output is not the final answer

Under the lower-bound candidate:

- UP transition-entry +8 same phase = 100%
- DOWN transition-entry +8 same phase = 100%
- RANGE transition-entry +8 same phase ≈ 0.35%
- median UP/DOWN episode length ≈ 196/189 bars
- median RANGE episode length = 1 bar

These values mainly reflect the sparse piecewise-linear graphical C2 update clock.

The continuity C2 completed-wave duration distribution itself is very slow:

- n = 170
- Q25 = 254 bars
- median = 377 bars
- Q75 = 534.25 bars

Eight native bars are only a small fraction of a typical C2 wave.

Therefore the computed V1.1 +8 persistence is retained as representation evidence, not accepted as the requested continuous low-frequency phase-persistence result.

## Implication

The next required gate is a **continuous C2 phase-carrier fidelity study**.

A continuous per-native-bar carrier may be considered only if:

1. its physical scale is fixed from the already-known graphical C2 wave-duration distribution, not from persistence or PnL;
2. it is causal;
3. it reproduces graphical C2 morphology/direction/turn timing with a preregistered fidelity gate;
4. it uses no future return or trading outcome.

Only after that fidelity gate passes may the UP/RANGE/DOWN deadband and +8 phase persistence study be repeated on the continuous carrier.

## Authority

No signal, strategy selection, trade, router, PnL-selection, paper/live or production authority.

The frozen current-band five-state classifier and accepted t+8 wrapper remain unchanged.
