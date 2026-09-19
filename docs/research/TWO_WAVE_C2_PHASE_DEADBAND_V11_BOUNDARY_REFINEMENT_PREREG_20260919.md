# Two-Wave C2 phase deadband V1.1 — boundary refinement preregistration

Issue #432. This is a pre-results refinement of the structural deadband search after the coarse V1 grid hit its lower boundary.

## Why V1.1 is needed

The first structural-only V1 execution used the preregistered coarse grid:

- exit: 0.0, 0.1, ..., 1.0
- enter: 0.1, 0.2, ..., 3.0

Its best feasible point was at the lower search boundary `exit=0.0, enter=0.1`.

Five calendar years independently selected the same pair, while 2016 had no feasible pair because the best coarse-grid re-entry-within-8 rate was 0.8709677, below the frozen 0.90 gate.

Because the candidate touched the lower grid boundary and one year narrowly failed only the timing gate, the coarse result is classified as:

`BOUNDARY_RESOLUTION_INSUFFICIENT__PERSISTENCE_NOT_FINAL`

The coarse +8 persistence output is quarantined and may not select V1.1 parameters.

## Frozen object and semantics

Unchanged from V1:

- object: actual graphical `C2 = S1 - S2`
- carrier: scale-specific continuity hierarchy
- causal normalized slope: C2 tail slope divided by recent known C2 `A2/T2`
- states: C2_UP / C2_RANGE / C2_DOWN
- direct UP<->DOWN transition forbidden
- RANGE is the mandatory exit/re-entry buffer

## Fine grid

Refine only the lower-bound region:

- exit = 0.00, 0.01, ..., 0.20
- enter = 0.01, 0.02, ..., 0.30
- require `enter >= exit + 0.01`

Therefore every candidate has a strictly positive deadband width.

No threshold outside this grid may be introduced after V1.1 outcomes.

## Structural feasibility

Unchanged:

- candidate directional episode < 4 bars is chatter
- stable raw turn requires new raw sign run >= 4 bars
- stable directional entry reference requires raw sign run >= 8 bars
- exit old direction within 4 bars >= 0.90
- enter new direction within 8 bars >= 0.90
- full-sample reference support >= 30 for each timing metric
- year-specific reference support >= 20

No persistence, return or PnL target enters feasibility.

## Lexicographic selection

Among feasible candidates:

1. minimum total chatter
2. minimum short same-direction RANGE roundtrip count
3. minimum RANGE occupancy
4. minimum enter threshold
5. minimum exit threshold

This remains the minimum-intervention solution after the anti-chatter and timing constraints are satisfied.

## Strengthened temporal stability gate

A global deadband is `STABLE_GLOBAL` only if:

1. all six years 2015-2020 have at least one feasible candidate;
2. each usable year's independently selected thresholds are available;
3. for exit and enter separately:
   - normalized MAD <= 0.35
   - full range <= 0.75

If any year has no feasible candidate, status is:

`YEAR_FEASIBILITY_GAP`

and the conditional-deadband contingency is activated even when the threshold MAD among the other years is small.

If all six years are feasible but dispersion exceeds the limits, status is:

`HIGH_VARIANCE`.

## Boundary-limited interpretation

If the selected global enter threshold equals the minimum tested value 0.01, record:

`LOWER_BOUNDARY_LIMITED`.

The operational V1.1 candidate may still use 0.01, but the scientific conclusion is only that the structurally preferred positive deadband is no wider than the tested 0.01 resolution. It must not be described as an exact continuous optimum.

## Conditional contingency

Activated for either:

- YEAR_FEASIBILITY_GAP, or
- HIGH_VARIANCE.

The frozen families remain:

1. C2 pace `A2/T2` tertile
2. C2 period T2 tertile
3. evidence age since latest known S2 node tertile

Each family must use the same V1.1 fine grid.

A family is accepted only if:

- all three tertiles have >= 5,000 resolved bars;
- all three tertiles are structurally feasible;
- all six years become feasible within the applicable tertile mapping;
- median normalized threshold MAD is >=30% lower than unconditional dispersion when unconditional dispersion is defined;
- no tertile increases chatter >10% versus the unconditional minimum-intervention candidate on the same bars.

If the trigger was YEAR_FEASIBILITY_GAP and unconditional dispersion score is zero/undefined, the dispersion-reduction clause is replaced by: the family must remove the year-feasibility gap while preserving the no-chatter/minimum-intervention constraints.

If zero or multiple families pass, conditionality remains unresolved.

## Final +8 persistence

Only after global or unique conditional deadband is frozen.

For each phase UP/RANGE/DOWN report:

- bar-level endpoint same phase at k+8
- continuous same phase through k+8
- transition-entry endpoint same phase at +8
- transition-entry continuous same phase through +8
- episode-duration distribution
- 3x3 +8 transition matrix
- year-by-year 2015-2020

The primary answer to "after a phase appears, is it still there eight bars later?" is the **transition-entry** measure, not the arbitrary-bar occupancy measure.

## Governance

No PnL, future-return magnitude, trade outcome, routing, signal, or production authority.

The frozen five-state current-band classifier and accepted t+8 wrapper remain unchanged.
