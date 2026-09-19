# C1 directional carrier atlas — result

Issue #535. Parent #533 / #531 / #507 / #450.

## Status

`C1_DIRECTIONAL_CARRIER_ATLAS_COMPLETE`

Atlas only. No carrier is promoted from this result.

Universe:
- exact strict-v2 #507 T0 signal bars, 2018–2020
- N = 945
- all signals remain inside the frozen C1 current/+8 oracle support

Carriers:
- RETURN_H = sign(log close[k] / close[k-H])
- OLS_H = sign(OLS slope of log-close over the trailing H-bar window)
- H in {32, 42, 64, 86}

All carrier inputs use bars <= k only.

## Main result

### RETURN carriers

Best positive-direction candidate is RETURN_32:

- coverage: 100%
- current retrospective C1 balanced accuracy: **57.44%**
- future+8 retrospective C1 balanced accuracy: **51.96%**
- T0-side aligned fraction: 54.07%
- T0-side opposed fraction: 45.93%

Other RETURN horizons are near chance for future+8:

- RETURN_42: 49.84%
- RETURN_64: 46.40%
- RETURN_86: 47.02%

### OLS carriers

All OLS carriers are systematically below chance against the retrospective C1 direction.

Future+8 balanced accuracy:

- OLS_32: **40.75%**
- OLS_42: 42.44%
- OLS_64: 41.37%
- OLS_86: 42.85%

The pattern is directionally stable across 2018–2020.

For OLS_32 specifically:

- 2018 future+8 BA: 39.87%
- 2019: 37.92%
- 2020: 43.46%

Therefore its simple sign inverse would correspond descriptively to approximately:

- pooled future+8 BA: **59.25%**
- 2018: 60.13%
- 2019: 62.08%
- 2020: 56.54%

This sign inversion is a **post-atlas hypothesis**, not an accepted carrier.

## Independence from T0

OLS carriers are not mechanical copies of T0 side.

OLS_32:
- aligned with T0: 20.63%
- opposed to T0: 79.37%

This makes the inverse-OLS hypothesis structurally interesting for a C1-specific direction carrier.

## Interpretation

The atlas does not support a simple long-horizon raw-return carrier for future C1 direction.

It reveals a stronger structural clue:

> raw-price OLS trend direction over adjacent longer horizons is systematically anti-aligned with the retrospective C1=S0-S1 residual direction.

This is consistent with C1 being a residual/band component rather than the raw low-frequency trend itself.

A separate preregistered study is required before any inverse OLS carrier is promoted.

## Evidence identity

Implementation SHA256:
`6a136abc9c5bd2a317ca203a3d6e60c99c655d3e57ffe572e547db20880aaf33`

Carrier ledger SHA256:
`1a9c3b4fa120f758eafbdda6a47372d850ff4c175918b5c19c9c43e408a51f20`

Result SHA256:
`a51c1362f5115344035082b193d99b9550baf77d3cfc19001ca767d68118cf8d`

## Authority

No signal/router/trade/paper/live/production authority.
