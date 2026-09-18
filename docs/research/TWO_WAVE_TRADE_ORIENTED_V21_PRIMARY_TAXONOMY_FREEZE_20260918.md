# Two-Wave trade-oriented V2.1 — primary taxonomy freeze

Issues #409 / #415 / #417.

## Status

`PRIMARY_TAXONOMY_FROZEN`

The current-band-first five-state reference taxonomy is now frozen on 400 blind market panels.

This freeze covers the **primary current-band label only**. Parent/coarser context remains optional metadata and cannot change the primary label.

## Frozen primary states

- `CURRENT_UP`
- `CURRENT_RANGE`
- `CURRENT_DOWN`
- `LOW_AMPLITUDE_VETO`
- `FINER_SCALE_OUT_OF_BAND`

Technical `DATA_INVALID` remains outside the five market states.

## Reference process

The first 368-panel pass pair was invalidated by a label-blind FINER coverage audit and preserved as failed evidence.

V2.1 then rebuilt a 400-panel packet with:

- 400 unique panel IDs;
- 400 unique trading days;
- 240 random primary panels, 40/year for 2015-2020;
- 128 original challenge panels;
- 32 additional label-blind FINER-dominant coverage panels.

Two new independent primary-only passes were run from scratch.

During both primary passes:

- only the 64-bar native-5m current-band view ending at `t+8` was readable;
- blind inventory exposed only `panel_id + amplitude_gate`;
- 128/256 context views remained unopened;
- controlled inventory, old six-bucket labels, old failed passes, recognizer outputs, outcome and PnL were not used.

## Frozen pass identities

Pass A:

`fc3d25109fd844fb4dbe32732fd48297e28dcc509061e054cb3e18635bfe565d`

Pass B:

`882583327b12a2fcdc5de556725427d681d3131c7fd8d16282caa9be6704a225`

A/B:

- agreements: 250;
- disagreements: 150.

All 150 disagreements were adjudicated using only the same 64-bar primary evidence.

Direction disagreements used four 4-bar projection phases and robust same-phase migration.

Three FINER disagreements were retained as FINER because raw 1-2 bar oscillation materially overwhelmed the 4-bar current-band projection; finding a sparse >=4-bar pivot chain inside that noise was not treated as sufficient current-band structure.

## Final labels

Final count:

| State | Count |
|---|---:|
| CURRENT_UP | 149 |
| CURRENT_RANGE | 47 |
| CURRENT_DOWN | 159 |
| LOW_AMPLITUDE_VETO | 42 |
| FINER_SCALE_OUT_OF_BAND | 3 |

Final unresolved count: **0**.

Adjudication SHA256:

`e0d84d42d26852e32eb2f2c55419896fc574ee8a6bdadf2084d9c44c87aa8a5e`

Final primary-label SHA256:

`bcb72a35d45e0ceb385dba92cf40efec61d7d94a08c5d03bffad047798a033c8`

## Post-freeze readback audit

Only after the primary labels were frozen was controlled sampling metadata reopened for aggregate verification.

Results:

- LOW amplitude gate consistency: 42 / 42 exact;
- random PRIMARY 240:
  - CURRENT_UP 101
  - CURRENT_RANGE 26
  - CURRENT_DOWN 103
  - LOW_AMPLITUDE_VETO 10
  - FINER_SCALE_OUT_OF_BAND 0
- the three FINER cases occur only in the dedicated coverage challenge:
  - one at 82.367bp;
  - one at 86.441bp;
  - one at 163.545bp.

Thus FINER is rare in random development sampling and is not equivalent to high amplitude.

The challenge strata are not prevalence estimates.

## Semantics confirmed by freeze

The governing priority is:

1. invalid technical evidence;
2. low-amplitude veto;
3. current-band structure existence;
4. if current-band structure exists: UP / RANGE / DOWN;
5. only if current-band structure fails and finer repeated oscillation dominates: FINER.

A broader parent or multiscale competition never overrides a valid current-band wave.

## Next phase

Design a retrospective recognizer against this frozen primary oracle.

The recognizer should initially use only the same current-band information set:

- native 5m;
- 64-bar current-band geometry;
- evidence through exactly `t+8`;
- frozen 17-bar amplitude veto.

The 128/256 context is not required to determine the primary five-state label.

Only after a retrospective recognizer is accepted and frozen may the fixed `8 × native 5m` delayed-causal retrospective-equivalent wrapper be built.

## Authority

No signal, trade, router, PnL-selection, paper/live or production authority is granted.
