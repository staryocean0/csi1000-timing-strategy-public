# R0 — explicit C2/C3 bandpass representation freeze result

Issue #452. Parent #450.

## Verdict

`R0_BANDPASS_REPRESENTATION_FROZEN`

The explicit retrospective graphical bandpass objects are now frozen for the frequency-routing thread.

## Frozen definitions

Low-pass skeletons:

- S1 = stage-2 input stream
- S2 = stage-3 input stream
- S3 = stage-4 input stream

Explicit residuals:

- `C2(t)=log S1(t)-log S2(t)`
- `C3(t)=log S2(t)-log S3(t)`

Interpolation uses occurrence-bar coordinates only and is restricted to common node support. No extrapolation is used.

## Source

- 000852.SH
- native 5m
- 2015–2020 development
- rows: 70,114
- SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

## Hierarchy capacity

- stage1 stream nodes: 2,648
- stage2 stream nodes / S1: 673
- stage3 stream nodes / S2: 171
- stage4 stream nodes / S3: 40

Completed waves by stage:

- stage1: 672
- stage2: 170
- stage3: 39
- stage4: 8

Pivots by stage:

- 1,347 / 344 / 80 / 20

Each stage remains a single continuity root in this representation.

## Support

C2=S1-S2:

- left: 266
- right: 69,880
- bars: 69,615

C3=S2-S3:

- left: 523
- right: 69,433
- bars: 68,911

Joint C2/C3 support:

- left: 523
- right: 69,433
- bars: **68,911**
- fraction of all source bars: **98.2842%**

The frozen >=90% support gate passes.

## Numerical identities

Maximum reconstruction errors:

- `S1 - (C2+S2)`: 0.0
- `S2 - (C3+S3)`: 0.0
- `S1 - (C2+C3+S3)`: 0.0

Tolerance gate: <=1e-12.

All pass.

## Residual sanity

C2:

- std: 0.0250246310
- min: -0.0369290562
- max: 0.2083201872

C3:

- std: 0.0815610504
- min: -0.0505215496
- max: 0.5763183871

All 68,911 joint rows are finite and both residuals have nonzero variation.

## Determinism

A second independent in-process build produced exact row-for-row equality and identical metadata.

Verdict:

`DETERMINISTIC_REPLAY_EXACT`

## Evidence identity

Implementation SHA256:

`10f620fc1d08e8d82bda2e1c41b1ea546c89c27673057ad726f19d42d0c689f7`

Joint ledger SHA256:

`0e632a2b782194f8d5d433ffd019780845de8f1d0b8a3e12124351073008e3ec`

Execution result SHA256:

`046cb5d665245261edcf93fee359e6bd9c8748d0ad0e6e4d41f46379ea9bbf84`

## Interpretation boundary

R0 proves only that the explicit retrospective C2/C3 bandpass residual representation is mathematically well-defined, high-coverage, deterministic and exactly reconstructive.

R0 does not establish:

- causal current-bar observability;
- C2/C3 state labels;
- phase definitions;
- thresholds;
- lead/lag usefulness;
- T0/C1 routing utility;
- signal/trade/production authority.

R1 is now authorized to inspect intrinsic C2/C3 morphology without execution outcomes.
