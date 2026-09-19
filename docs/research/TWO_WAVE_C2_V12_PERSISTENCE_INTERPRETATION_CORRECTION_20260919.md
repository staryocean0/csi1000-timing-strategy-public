# Two-Wave C2 V1.2 persistence interpretation correction

Issue #432 / semantic-threshold follow-up #444.

## Status

`DENSE_C2_PERSISTENCE_INTERPRETATION_CORRECTED`

The dense retrospective graphical C2 evidence remains valid as morphology evidence.

The previous interpretation:

> directional C2 UP/DOWN +8 persistence proves that an 8-bar delayed follower retains structural value

is withdrawn.

## Why the earlier interpretation is invalid

Dense retrospective C2 is constructed from the completed scale-specific-continuity hierarchy:

`C2(t)=log S1(t)-log S2(t)`

with linear interpolation between sparse structural nodes on occurrence-time coordinates.

This creates long piecewise-linear directional segments.

Direct audit of the frozen V1.2 phase episodes shows:

- C2_UP episodes: 192
- minimum C2_UP episode length: 29 native 5m bars
- median C2_UP episode length: 165.5 bars
- all 192 C2_UP episodes remain UP through +8 and through +16

- C2_DOWN episodes: 194
- one 1-bar exceptional episode
- 193/194 remain DOWN through +8 and +16
- median C2_DOWN episode length: 140.5 bars

Therefore the previously reported:

- C2_UP transition-entry +8 same phase = 100%
- C2_DOWN transition-entry +8 same phase = 99.48%

are largely consequences of the retrospective interpolation geometry.

They are not evidence that a causal phase recognized with 8 bars of delay will continue afterward.

## Correct delay-following estimand

If a retrospective phase begins at occurrence time `t` and a future causal recognizer first makes it usable at `t+8`, then the relevant follow-on question is not only:

`phase(t+8) == phase(t)`.

The required post-recognition outcomes include:

1. eligibility after delay:
   `phase(t+8) == phase(t)`;

2. another-eight-bar survival:
   `phase(t+16) == phase(t)`, conditional on the phase still being alive at t+8;

3. continuous residual survival:
   phase remains unchanged for every bar in `t+9 ... t+16`;

4. residual episode life:
   `episode_end - (t+8)`, conditional on episode_end > t+8;

5. reversal / decay hazard measured only after `t+8`.

These quantities must be evaluated against a causal recognizer or carrier whose knowledge boundary is explicit.

## Semantic RANGE correction

The frozen V1.2 deadband `exit=0.00 / enter=0.01` is retained only as:

`MINIMUM_ANTI_CHATTER_BUFFER_EVIDENCE`.

It is not accepted as the semantic boundary of the true large-cycle horizontal phase.

Reason:

- its optimization objective explicitly minimized chatter and then RANGE occupancy;
- it therefore tends to select the narrowest feasible buffer;
- the resulting RANGE episodes are overwhelmingly 1-bar reversal bridges;
- that is compatible with an exit buffer but does not define the full market-semantic C2 RANGE phase.

## Required next phase

The semantic C2 UP/RANGE/DOWN oracle must be defined independently of the small/current-band slope threshold being calibrated.

The new workflow is:

1. build blinded large-cycle graphical C2 phase panels;
2. annotate true large-cycle UP/RANGE/DOWN regions without exposing current-band low-point-line slope values;
3. map the frozen current-band low-point-line slope / normalized migration `g` into those oracle regions;
4. estimate the slope intervals associated with large-cycle UP/RANGE/DOWN;
5. estimate threshold dispersion by C2 wave and calendar year;
6. if dispersion is high, test preregistered structural conditions rather than using one global average;
7. only after semantic thresholds freeze, build a causal delayed recognizer and evaluate post-`t+8` residual persistence.

## Governance

No historical evidence is deleted.

The V1.2 morphology files remain valid evidence of the retrospective graphical construction.

What is superseded is the causal/delay-following interpretation of the 100% / 99.48% directional persistence numbers.

No PnL, return, signal, routing, trade, paper/live, or production authority.
