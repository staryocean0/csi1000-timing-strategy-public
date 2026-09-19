# Two-Wave dense retrospective C2 phase V1.2 — structural deadband freeze

Issue #432.

## Status

`DENSE_C2_STRUCTURAL_DEADBAND_FROZEN__PERSISTENCE_NOT_YET_OPENED`

This checkpoint freezes the three-state C2 deadband before any V1.2 +8 persistence result is computed.

## Dense retrospective carrier

Authoritative object remains the accepted graphical hierarchy:

`C2(t)=log S1(t)-log S2(t)`

where S1 and S2 are linearly interpolated on occurrence-bar coordinates inside their common support.

This is retrospective morphology only. No causal-equivalence claim is made here.

Frozen carrier audit:

- common occurrence support: 69,615 bars
- normalized usable bars: 69,358
- first usable bar: 523
- last usable bar: 69,880
- completed continuity-C2 waves: 170
- raw sign changes: 386
- raw sign runs: 387
- median raw sign-run length: 157 bars
- raw sign runs shorter than 4 bars: 1

Dense C2 ledger SHA256:

`728d2a6c50a7add6fd2daffa2cf4acd207940e6ed38e100e95d5048eef4d3101`

## Normalized slope

`z(t)=[C2(t)-C2(t-1)] / median(latest up to 3 completed C2 A2/T2 with end_bar<=t)`

No persistence target participates in z construction.

## Frozen Schmitt semantics

- RANGE -> UP if z >= +enter
- RANGE -> DOWN if z <= -enter
- UP -> RANGE if z <= +exit
- DOWN -> RANGE if z >= -exit
- direct UP <-> DOWN is forbidden

RANGE is therefore a mandatory anti-chatter / exit state.

## Fine-grid structural result

Frozen grid:

- exit = 0.00..0.20 step 0.01
- enter = 0.01..0.30 step 0.01
- require enter >= exit + 0.01

420 pairs evaluated.

336 pairs satisfy the preregistered structural timing gates.

Lexicographic structural optimum:

- exit = `0.00`
- enter = `0.01`

Full-sample diagnostics:

- stable raw turns: 385
- stable >=8-bar raw runs: 386
- exit old direction within 4 bars: `1.000000`
- enter new direction within 8 bars: `0.9896373056994818`
- short directional episodes <4 bars: 1
- short same-direction RANGE roundtrips: 0
- total chatter: 1
- RANGE occupancy: `0.017748493324490324`
- transitions: 770

## Parameter dispersion

Independent structural optimization by calendar year:

| Year | exit | enter | chatter | exit<=4 | enter<=8 |
|---|---:|---:|---:|---:|---:|
| 2015 | 0.00 | 0.01 | 1 | 100% | 96.43% |
| 2016 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2017 | 0.00 | 0.01 | 0 | 100% | 97.26% |
| 2018 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2019 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2020 | 0.00 | 0.01 | 0 | 100% | 100% |

All 6/6 years are feasible.

Threshold dispersion:

- exit median 0.00, MAD 0.00, full range 0.00
- enter median 0.01, MAD 0.00, full range 0.00

Verdict:

`STABLE_GLOBAL`

The predeclared conditional-deadband contingency is not activated.

## Boundary-limited interpretation

The selected enter threshold equals the minimum positive grid value 0.01.

Therefore this freeze is also:

`LOWER_BOUNDARY_LIMITED`

The scientific statement is not that 0.01 is the exact continuous optimum.

It is only that, at the tested resolution, a wider deadband is not structurally required to satisfy the anti-chatter/timing constraints.

## Evidence identities

- dense C2 ledger:
  `728d2a6c50a7add6fd2daffa2cf4acd207940e6ed38e100e95d5048eef4d3101`
- global grid:
  `957091f479778292d836c17ec58b03822ac96015e503d012efa6ee22ee3176c8`
- annual optima:
  `16f3330c129fe756bd8bdf19779dff9bd09a0a78280c6d977d258dad51177254`
- structural result:
  `7a8427d9e9a7d3f577edca6334b3b68a6b6d3ef6256ca3e2ea29c96b3210f973`

## Next step

Only after this freeze is merged may V1.2 +8 phase persistence be opened.

No threshold may change after persistence is observed.

## Authority

No PnL, future return, signal, trade, router, paper/live or production authority.
