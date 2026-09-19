# R0 — explicit C2/C3 bandpass representation freeze preregistration

Issue #452. Parent #450.

## Objective

Freeze the explicit retrospective graphical bandpass representation before any state-machine or execution-outcome analysis.

## Frozen source

- symbol: 000852.SH
- timeframe: native 5m
- development years: 2015–2020
- rows: 70,114
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

## Hierarchy construction

Use the already accepted scale-specific continuity recursion:

`continuity_hierarchy(base_inventory(bars), minimum=1, depth=4)`.

Map streams to low-pass skeletons:

- stage 2 input stream = S1
- stage 3 input stream = S2
- stage 4 input stream = S3

No alternate smoothing/filtering family is allowed in R0.

## Explicit residuals

On occurrence-bar coordinates:

- interpolate log(S1)
- interpolate log(S2)
- interpolate log(S3)

Only use the intersection of the first/last occurrence support of all required node streams.

Define:

`C2(t)=log S1(t)-log S2(t)`

`C3(t)=log S2(t)-log S3(t)`

No extrapolation outside common support.

## Required identities

On the joint support, numerical error must satisfy <=1e-12 for:

- `log S1 = C2 + log S2`
- `log S2 = C3 + log S3`
- `log S1 = C2 + C3 + log S3`

## Required audits

Report:

- node counts for S1/S2/S3
- completed-wave counts at hierarchy stages 1–4
- individual C2 support
- individual C3 support
- joint support
- joint support fraction of source bars
- finite-value count
- min/max/standard deviation of C2 and C3
- zero-variance guard
- monotonic occurrence coordinates
- duplicate occurrence count
- reconstruction errors
- deterministic replay equality

## Acceptance

R0 passes only if:

1. source SHA matches exactly;
2. all node streams have strictly increasing occurrence coordinates;
3. no duplicate occurrence coordinate exists within each skeleton stream;
4. C2 and C3 are finite on every joint-support row;
5. both residuals have nonzero variance;
6. all three reconstruction errors <=1e-12;
7. second independent build is exactly equal row-for-row;
8. joint support fraction >=0.90.

## Scientific boundary

This is a retrospective morphology representation freeze.

R0 does not claim:

- causal current-bar availability;
- state labels;
- phase labels;
- trend direction;
- thresholds;
- lead/lag usefulness;
- T0/C1 execution utility;
- signal/router/trade/production authority.

R1 may inspect intrinsic C2/C3 morphology only after R0 passes.
