# C1 lead-8 compression specificity under evidence-age rematching — result

Issue #493. Parent #485 / #483 / #450.

## Verdict

`C1_LEAD8_COMPRESSION_SPECIFICITY_SUPPORTED`

The pre-turn compression signal survives stricter matching on information-age variables.

## Support

- eligible events: 1,521
- matched events: 1,501
- event coverage: 98.685%
- control rows: 7,445
- median controls per event: 5
- unique control bars: 7,405
- max reuse count: 3
- reuse slots: 40

## Balance after rematching

Event minus matched-control median difference:

- base confirmation age: 0 bars, bootstrap CI [0,0]
- causal C1 evidence age: 0 bars, bootstrap CI [0,0]

Thus the compression result is not explained by fresher hierarchy evidence.

## Primary variables

### abs_ret_8

- event median: 0.0026040
- control median: 0.0034792
- paired median difference: -0.0008137
- 95% CI: [-0.0009970, -0.0006749]
- negative in 6/6 years
- negative for OLD_UP and OLD_DOWN

### range_8

- event median: 0.0049469
- control median: 0.0060380
- paired median difference: -0.0009085
- 95% CI: [-0.0010904, -0.0006503]
- negative in 6/6 years
- negative for OLD_UP and OLD_DOWN

### rv_8

- event median: 0.0010847
- control median: 0.0012976
- paired median difference: -0.0001678
- 95% CI: [-0.0002104, -0.0001191]
- negative in 6/6 years
- negative for OLD_UP and OLD_DOWN

### efficiency_8

- event median: 0.34765
- control median: 0.39982
- paired median difference: -0.04195
- 95% CI: [-0.06310, -0.02422]
- negative in 5/6 years
- negative for OLD_UP and OLD_DOWN

All 4/4 preregistered variables pass the compression criterion.

## Interpretation

The robust precursor is not terminal acceleration.

Eight bars before a final retrospective C1 turn, the market is typically:

- moving less in absolute terms;
- trading in a narrower range;
- realizing lower short-horizon volatility;
- traversing the path less efficiently.

This supports a direction-agnostic interpretation:

> an upcoming C1 turn is preceded by compression/exhaustion rather than an already-visible reversal.

The variables are unsigned and available at the decision clock, so they can be used in a later genuinely causal turn-risk ranking without knowing the future turn direction.

## Evidence identity

- module SHA256: `ebeed66674b52abb81901a74acacb7496f1cd1dbe452f46cecfc2442cee1a28e`
- events ledger SHA256: `9723fdc08adcab6d325b6bda450acec4caac9c734a05013911926f749dae8d06`
- matches ledger SHA256: `996c3ecfe5559a50066a37b8f5c96ef34ae09ecf6c3d159d873c8ef7931a662b`
- paired ledger SHA256: `e18edc0aabea3fe3e22d3e0b03a6ae61029a474f83ae8819eb1726d65dcef64f`
- exact result SHA256: `5055881f7624cf2d7f267c257332007d5b2143ff201afcc8e8e3c65da9c3c7e3`

## Boundary

No T0/C1 PnL or routing outcomes were used.

This is precursor evidence only, not a signal or live router.
