# R2 — C2/C3 bandpass exact causal observability preregistration

Issue #458. Parent #450.

## Objective

Measure when the frozen retrospective C2/C3 bandpass morphology becomes exactly knowable from confirmed hierarchy nodes.

No routing or trading outcome is used.

## Frozen objects

Use the accepted scale-specific continuity hierarchy at depth 4.

- S1 = stage-2 input stream
- S2 = stage-3 input stream
- S3 = stage-4 input stream
- C2 = log(S1)-log(S2)
- C3 = log(S2)-log(S3)

Use the R0 frozen joint occurrence support.

## Exact knowledge clock

For occurrence bar t, the final interpolated skeleton value at t is determined by the two final adjacent nodes bracketing t in that skeleton.

For slope at t, both t and t-1 are required.

For each skeleton Sk, define:

`K_Sk(t) = max(known_from_bar of all final bracketing nodes required for t and t-1)`.

Then:

- `K_C2(t)=max(K_S1(t),K_S2(t))`
- `K_C3(t)=max(K_S2(t),K_S3(t))`
- `K_joint(t)=max(K_S1(t),K_S2(t),K_S3(t))`

Exact knowledge delays:

- `D_C2(t)=K_C2(t)-t`
- `D_C3(t)=K_C3(t)-t`
- `D_joint(t)=K_joint(t)-t`

Negative delays are invalid and fail the audit.

## Required outputs

Overall and by year:

- delay count / mean / std / q01/q05/q25/q50/q75/q90/q95/q99 / max
- exact-knowledge availability within delays:
  - 0
  - 4
  - 8
  - 16
  - 32
  - 64
  - 128
  - 256
  - 512 native 5m bars

For retrospective slope-sign relation (++,+-,-+,--):

- support
- joint delay distribution
- availability within the same delay grid

At retrospective C2 and C3 slope-turn bars:

- turn count
- exact-knowledge delay distribution
- availability within the same delay grid

## Prefix replay

At cuts 10,000 / 30,000 / 50,000:

1. rebuild the hierarchy from the source prefix;
2. compare each prefix S1/S2/S3 stream against the full hierarchy nodes whose known_from_bar is within the prefix;
3. occurrence_bar, known_from_bar and price must match exactly.

Any mismatch fails the prefix replay gate.

## Interpretation

R2 measures exact observability of the frozen retrospective morphology.

It does not require exact state to be available quickly.

If delays are too large for execution routing, the correct next step is a separate causal recognizer/carrier study. Retrospective states may not be backfilled into live decisions.

## Forbidden

No T0 outcome, C1 outcome, PnL, future return, route winner, state-machine threshold or strategy selection.

## Authority

No signal/router/trade/paper/live/production authority.
