# Two-Wave C2 phase deadband V1.1 — structural freeze

Issue #432.

## Status

`STRUCTURAL_DEADBAND_FROZEN__PERSISTENCE_NOT_YET_COMPUTED`

This freeze is strictly pre-persistence. No +8 persistence result was used to select the C2 phase deadband.

## Carrier identity

Research object:

`C2 = S1 - S2`

from the accepted scale-specific continuity hierarchy.

Hard carrier identity:

- source rows: 70,114
- source SHA256:
  `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`
- causal graphical C2 ledger rows: 69,372
- raw nonzero-sign changes: 289
- C2 ledger SHA256:
  `7191f0ca6b762edff0967117112c3b6ead09ae6d7424da4ced61909ad7f3071c`

Any result not matching this carrier identity is invalid.

A separate concurrent P320/Q1 IIR-proxy run was explicitly quarantined as `INVALID_CARRIER_CONTAMINATION` and is excluded from scientific adjudication.

## Frozen normalized slope

At knowledge bar k:

`z(k) = [tail_log_slope(S1)-tail_log_slope(S2)] / median(recent known C2 A2/T2)`.

Only nodes and completed C2 waves known by k are used.

No future node is backfilled.

## Frozen Schmitt semantics

States:

- C2_UP
- C2_RANGE
- C2_DOWN

Transitions:

- RANGE -> UP when z >= enter
- RANGE -> DOWN when z <= -enter
- UP -> RANGE when z <= exit
- DOWN -> RANGE when z >= -exit
- direct UP <-> DOWN transition forbidden

RANGE is therefore the mandatory anti-chatter / exit buffer.

## V1.1 fine-grid result

Frozen fine grid:

- exit = 0.00 ... 0.20, step 0.01
- enter = 0.01 ... 0.30, step 0.01
- require enter >= exit + 0.01

420 candidate pairs were evaluated.

210 pairs passed the preregistered structural timing gates.

Lexicographic structural optimum:

- exit = `0.00`
- enter = `0.01`
- deadband width = `0.01`

Full-sample diagnostics:

- stable raw turns: 289
- stable >=8-bar raw directional runs: 290
- exit old direction within 4 bars: `1.000000`
- enter new direction within 8 bars: `0.996551724137931`
- directional episodes shorter than 4 bars: 0
- short same-direction RANGE roundtrips: 0
- total chatter count: 0
- RANGE occupancy: `0.005174998558496223`
- phase transitions: 576

## Temporal parameter stability

Independent yearly structural optimization:

| Year | exit | enter | chatter | exit<=4 | enter<=8 |
|---|---:|---:|---:|---:|---:|
| 2015 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2016 | 0.00 | 0.01 | 1 | 100% | 98.39% |
| 2017 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2018 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2019 | 0.00 | 0.01 | 0 | 100% | 100% |
| 2020 | 0.00 | 0.01 | 0 | 100% | 100% |

All six years are feasible.

Dispersion:

- exit median = 0.00
- exit MAD = 0.00
- exit full range = 0.00
- enter median = 0.01
- enter MAD = 0.00
- enter full range = 0.00

Verdict:

`STABLE_GLOBAL`

The preregistered conditional-deadband contingency is **not activated**.

There is no evidence in this development sample that year-specific or condition-specific thresholds are needed.

## Boundary-limited interpretation

The selected enter threshold equals the minimum positive grid value `0.01`.

Therefore scientific status includes:

`LOWER_BOUNDARY_LIMITED`

This does **not** mean the continuous mathematical optimum is exactly 0.01.

It means:

> within the preregistered positive-width grid, the minimum-intervention anti-chatter solution is at or below 0.01 times the recent C2 normal pace A2/T2.

The operational V1.1 phase process uses 0.01 because a strictly positive RANGE buffer was preregistered as mandatory.

A future finer-resolution study may test whether the necessary positive width is smaller, but may not use persistence/PnL to choose it.

## Evidence identities

- C2 ledger SHA256:
  `7191f0ca6b762edff0967117112c3b6ead09ae6d7424da4ced61909ad7f3071c`
- global grid SHA256:
  `18197e05ac8eaf50eaa206ec56b9a0929224b37adeb9255743788eeac795043c`
- annual optima SHA256:
  `65eb11602029205171ad3f8b7b70ad26579ae7c5c86175773b02bee44588f879`
- structural result SHA256:
  `0812955df47a1bf9fbde445e4882466bb54f8a02a3d445ae97ac7c9efd2b80f2`

## Next step

With the deadband now frozen structurally, compute the predeclared +8 persistence outcomes:

- transition-entry endpoint same phase
- transition-entry continuous same phase
- bar-level endpoint and continuous persistence
- 3x3 +8 transition matrix
- yearly 2015-2020

No threshold may change after persistence is opened.

## Authority

No PnL, future-return target, signal, strategy selection, trade, router, paper/live or production authority.
