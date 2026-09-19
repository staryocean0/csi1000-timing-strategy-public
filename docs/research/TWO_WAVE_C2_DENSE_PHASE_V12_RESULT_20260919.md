# Two-Wave dense retrospective C2 phase V1.2 — final result

Issue #432.

## Final status

`DENSE_C2_PHASE_ADJUDICATED__GLOBAL_DEADBAND_STABLE__DIRECTIONAL_T8_PERSISTENCE_SUPPORTED__RANGE_T8_NOT_SUPPORTED`

This is the first result in this line that measures the actual dense retrospective graphical C2 morphology at every native 5m occurrence bar.

The previous sample-and-hold as-of descriptor is excluded from persistence adjudication because its structural updates were too sparse.

## 1. Research object

Use the accepted scale-specific-continuity hierarchy.

On common occurrence support:

- interpolate log(S1) at every native 5m bar;
- interpolate log(S2) at every native 5m bar;
- define `C2(t)=log S1(t)-log S2(t)`.

Dense slope: `s(t)=C2(t)-C2(t-1)`.

Normalize by the median recent completed-C2 pace `A2/T2`.

This is a retrospective morphology oracle. It is not yet a causal live signal.
## 2. Dense carrier audit

Frozen audit is reproduced exactly:

- common support: 69,615 bars
- normalized usable bars: 69,358
- first usable bar: 523
- last usable bar: 69,880
- complete C2 waves: 170
- raw sign changes: 386
- raw sign runs: 387
- median raw sign-run length: 157 bars
- raw sign runs shorter than 4 bars: 1

Dense C2 ledger SHA256:

`728d2a6c50a7add6fd2daffa2cf4acd207940e6ed38e100e95d5048eef4d3101`

## 3. RANGE deadband / anti-chatter result

Frozen three-state Schmitt logic:

- RANGE -> UP if z >= +enter
- RANGE -> DOWN if z <= -enter
- UP -> RANGE if z <= +exit
- DOWN -> RANGE if z >= -exit
- direct UP <-> DOWN forbidden

Frozen structural optimum before persistence:

- exit = `0.00`
- enter = `0.01`
Structural diagnostics:

- stable raw turns: 385
- stable >=8-bar directional runs: 386
- exit old direction within 4 bars: **100%**
- enter new direction within 8 bars: **98.96%**
- short same-direction RANGE roundtrips: **0**
- total chatter: 1
- RANGE occupancy: **1.77%**

The selected RANGE interval therefore performs the requested anti-chatter / exit-buffer role.

## 4. Parameter variance

Independent optimization for every year 2015-2020 selects exactly:

`exit=0.00 / enter=0.01`

Therefore:

- exit MAD = 0
- exit full range = 0
- enter MAD = 0
- enter full range = 0
- all 6/6 years feasible

Verdict: `STABLE_GLOBAL`.

The predeclared conditional-parameter branch is not activated.

There is no evidence in this development sample that the RANGE deadband requires a year-specific or condition-specific parameter.

The selected enter threshold is still `LOWER_BOUNDARY_LIMITED`: 0.01 is the minimum positive tested resolution, not a claim of an exact continuous optimum.
## 5. Primary persistence result: after a phase appears, is it still present 8 bars later?

Primary unit is a transition into the retrospective phase.

| Phase entered | Entries | Median episode length | Same phase at +8 | Continuous same through +8 |
|---|---:|---:|---:|---:|
| C2_UP | 192 | 165.5 bars | **100.00%** | **100.00%** |
| C2_RANGE | 385 | 1 bar | **1.04%** | **1.04%** |
| C2_DOWN | 194 | 140.5 bars | **99.48%** | **99.48%** |

This cleanly separates the three phases.

UP and DOWN have substantial remaining life after eight native 5m bars.

RANGE generally does not.

## 6. Year-by-year transition-entry persistence

UP:

- 2015-2020: +8 same-phase = 100% in all six years

DOWN:

- 2015: 96.55%
- 2016-2020: 100%

RANGE:

- 2015: 3.57%
- 2016: 0%
- 2017: 2.82%
- 2018: 0%
- 2019: 0%
- 2020: 0%
Thus the directional +8 persistence is temporally stable in this development sample, while RANGE is consistently short-lived.

## 7. RANGE semantics

RANGE episodes:

- count: 385
- median length: 1 bar
- 98.96% shorter than 4 bars

Bridge structure:

- DOWN -> RANGE -> UP: 192 episodes
- UP -> RANGE -> DOWN: 192 episodes
- DOWN -> RANGE -> DOWN: 1 long episode
- short same-direction RANGE roundtrips: 0

Therefore RANGE is not behaving as an ordinary long-lived horizontal regime under the minimum-intervention anti-chatter objective.

Its dominant role is:

> **exit / reversal buffer between opposite directional phases.**

This matches the intended anti-chatter responsibility.
## 8. What the eight-bar delay means

For directional C2 phases:

- eight bars is much shorter than the typical phase duration;
- median UP episode = 165.5 bars;
- median DOWN episode = 140.5 bars;
- a phase recognized eight bars after its occurrence would almost always still be directionally alive in this retrospective morphology.

Therefore:

`UP/DOWN: T+8 FOLLOWING HAS STRUCTURAL VALUE`

For RANGE:

- median duration = 1 bar;
- only 1.04% of RANGE entries still exist eight bars later.

Therefore:

`RANGE: T+8 FOLLOWING DOES NOT HAVE EXIT-TIMING VALUE`

If RANGE is intended as the exit point, waiting eight native bars to recognize it is too late.
## 9. Secondary bar-level +8 persistence

Occupancy-weighted results:

- C2_UP:
  - support 35,690 bars
  - same phase at +8 = 95.70%
- C2_DOWN:
  - support 32,429 bars
  - same phase at +8 = 95.26%
- C2_RANGE:
  - support 1,231 bars
  - same phase at +8 = 66.45%

The bar-level RANGE figure is not the primary answer because it is dominated by the very small number of unusually long RANGE intervals.

For the question "after RANGE first appears, is it still there eight bars later?", the correct measure is the 1.04% transition-entry result.

## 10. +8 transition matrix

From C2_UP:

- UP: 95.70%
- RANGE: 0.54%
- DOWN: 3.77%

From C2_DOWN:

- DOWN: 95.26%
- RANGE: 0.68%
- UP: 4.06%

From C2_RANGE:

- RANGE: 66.45%
- UP: 17.30%
- DOWN: 16.25%
Again, occupancy-conditioned RANGE and transition-entry RANGE answer different questions and must not be conflated.

## 11. Scientific boundary

V1.2 is retrospective-first.

It proves:

1. a stable global anti-chatter deadband exists for the dense graphical C2 morphology;
2. no conditional deadband is required by the observed parameter variance;
3. UP/DOWN have very high +8 residual persistence;
4. RANGE is primarily a short exit/reversal buffer and is usually gone long before +8.

V1.2 does **not** prove that this dense retrospective phase is causally knowable by t+8.

That is the next separate gate.

A delayed recognizer may not alter this retrospective oracle.
## 12. Evidence identities

Structural:

- dense ledger: `728d2a6c50a7add6fd2daffa2cf4acd207940e6ed38e100e95d5048eef4d3101`
- global grid: `957091f479778292d836c17ec58b03822ac96015e503d012efa6ee22ee3176c8`
- annual optima: `16f3330c129fe756bd8bdf19779dff9bd09a0a78280c6d977d258dad51177254`
- structural result: `7a8427d9e9a7d3f577edca6334b3b68a6b6d3ef6256ca3e2ea29c96b3210f973`

Persistence:

- entry summary: `d17931a84c47f573a16fbf383d5c83758330bbe36ca4bb88b472abeed29aee0a`
- yearly entry: `38a1a9eb8f99497c41a7d169a003df1c7850da925d86b1dff4b0b2e2346bdfbc`
- episode durations: `353205455fbfb589447e5984578bac7c596df1cb6c2494e7d4d14de62ee0d2c7`
- RANGE bridges: `2bc1dca57fd81ee3471584c6c6ce8b75997cdccc5a1cfd03179b10f8d6852c7e`
- transition matrix: `a31af2bd09dea050374cfbfc42dbfc60097ad5a5cc7683f41cf311696dca9d4a`
- persistence result: `99613ece49cbc431d0983b292e120716daedb8e38fb95dc63b8c3b488a15bbc2`

## 13. Governance

Post-persistence V1.2 deadband retuning is forbidden.

No PnL, future-return target, trade outcome, signal, router, paper/live or production authority.
