# Two-Wave C2 dense phase V1.2 — retrospective oracle preregistration

Issue #432.

## Why V1.2

The previous as-of tail-slope descriptor is useful as a realtime clock diagnostic, but its +8 persistence is mechanically inflated because the descriptor only updates when new S1/S2 nodes become known.

Clock audit:

- structural updates: 667
- median update gap: 89 native 5m bars
- every UP/DOWN entry had no structural update during the next 8 bars

Therefore the as-of sample-and-hold persistence is excluded from scientific phase-persistence adjudication.

V1.2 returns to retrospective-first research.

## Dense retrospective C2 curve

Use the accepted scale-specific-continuity hierarchy.

Let:

- S1 = occurrence-time low-node skeleton entering the C2 stage
- S2 = occurrence-time low-node skeleton entering the next stage

On the overlap of their occurrence supports:

- linearly interpolate log(S1) at every native 5m occurrence bar
- linearly interpolate log(S2) at every native 5m occurrence bar
- define dense `C2(t) = log S1(t) - log S2(t)`

No extrapolation outside common occurrence support.

This is a retrospective morphology oracle, not a causal realtime signal.

## Dense slope

`s(t)=C2(t)-C2(t-1)`

Normalize by recent retrospective C2 pace:

- use the latest up to three completed C2 waves with `end_bar <= t`
- `pace_i=A2_i/T2_i`
- `pace(t)=median(pace_i)`
- `z(t)=s(t)/pace(t)`

If no prior completed C2 wave is available, phase is UNRESOLVED.

Availability audit before phase outcomes:

- dense common support: 69,615 bars
- normalized usable bars: 69,358
- first usable bar: 523
- last usable bar: 69,880
- raw sign changes: 386
- raw sign runs: 387
- median raw sign-run length: 157 bars
- raw sign runs shorter than 4 bars: 1

## Three-state phase

States:

- C2_UP
- C2_RANGE
- C2_DOWN

Use the same mandatory Schmitt buffer:

- RANGE -> UP when z >= +enter
- RANGE -> DOWN when z <= -enter
- UP -> RANGE when z <= +exit
- DOWN -> RANGE when z >= -exit
- no direct UP <-> DOWN transition

RANGE is a real anti-chatter / exit state, not only z==0.

## Deadband grid

Use the already preregistered fine grid:

- exit = 0.00 ... 0.20, step 0.01
- enter = 0.01 ... 0.30, step 0.01
- require enter >= exit + 0.01

No wider search is allowed after results.

## Structural selection

Definitions remain:

- short directional episode: <4 bars
- stable raw turn: new raw sign run >=4 bars
- stable directional entry reference: raw sign run >=8 bars

A candidate is feasible only if:

- exit old direction within 4 bars >=90%
- enter new direction within 8 bars >=90%
- each timing metric has >=30 full-sample events

Select lexicographically:

1. minimum total chatter
2. minimum short same-direction RANGE roundtrips
3. minimum RANGE occupancy
4. minimum enter
5. minimum exit

No persistence target enters threshold selection.

## Parameter variance

Repeat structural optimization independently for 2015-2020.

Each year requires >=20 reference events for both timing metrics.

A single global deadband is stable only if all 6 years are feasible and:

- normalized MAD <=0.35 for exit and enter
- full range <=0.75 for exit and enter

Otherwise activate the same predeclared conditional families:

- C2 pace tertile
- C2 period tertile
- S2 occurrence-age tertile

## Phase persistence

Only after deadband freeze.

Primary question:

> If dense retrospective C2 phase first enters UP/RANGE/DOWN at occurrence bar t, is it still in the same phase at t+8?

Report:

- transition-entry endpoint same-phase at +8
- transition-entry continuous same-phase through +8
- episode-duration distribution
- bar-level endpoint and continuous +8 persistence
- 3x3 +8 transition matrix
- yearly 2015-2020

This directly measures whether an 8-bar recognition delay would still leave the original C2 phase alive.

## Delayed recognizer boundary

V1.2 does not yet claim the dense phase is causally knowable by t+8.

If retrospective persistence is useful, the next separate gate is to build a delayed recognizer and test exact retrospective equivalence.

## Governance

No PnL, future-return magnitude, trade outcome, signal, routing or production authority.
