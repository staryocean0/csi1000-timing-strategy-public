# Causal C1 relation × compression-risk interaction on T0 outcomes — preregistration

Issue #571. Parent #507 / #493 / #450.

## Objective

Test whether the accepted causal C1 compression-risk ranking has economically meaningful interaction with the then-known causal C1 relation to T0.

## Frozen inputs

Compression score/bands:
- authoritative #507 v2 only;
- walk-forward 2018/2019/2020;
- bands B1..B5 frozen from prior-only calibration;
- no re-estimation.

T0:
- period 21 own-lifecycle breakout module;
- use the same closed-trade net_log_return_proxy.

Causal C1 relation:
- use stage1 causal_state at the T0 signal bar k;
- if RESOLVED, map causal C1 leg UP/DOWN relative to T0 trade side;
- ALIGNED if same sign;
- OPPOSED if opposite sign;
- unresolved rows are excluded and reported.

## Analysis universe

Start from the 945 authoritative #507 scored T0 signal bars.

Join one-to-one to the corresponding T0 closed trade by signal_bar.

Require the future-8 target window to remain inside the frozen #507 C1 oracle support exactly as in authoritative v2.

## Primary 2×5 table

Rows:
- C1_ALIGNED
- C1_OPPOSED

Columns:
- B1 .. B5 frozen compression-risk bands.

For each cell report:
- N
- mean net bp
- median net bp
- win rate
- fast-loss rate
- mean duration.

Also report each row by test year.

## Primary contrasts

Within ALIGNED:
Delta_A = mean_net(B5) - mean_net(B1).
Expected sign: negative.

Within OPPOSED:
Delta_O = mean_net(B5) - mean_net(B1).
Expected sign: positive.

Interaction:
I = Delta_O - Delta_A.

Expected sign: positive.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

Bootstrap 5,000 block resamples, seed 20260919.

Report 95% CI for:
- Delta_A
- Delta_O
- I.

## Interaction gate

`C1_COMPRESSION_T0_INTERACTION_SUPPORTED` iff all are true:

1. point Delta_A < 0;
2. point Delta_O > 0;
3. interaction I > 0;
4. bootstrap 95% lower bound for I > 0;
5. ALIGNED B5 mean < ALIGNED B1 mean in at least 2 of 3 test years;
6. OPPOSED B5 mean > OPPOSED B1 mean in at least 2 of 3 test years.

Delta_A and Delta_O individual CIs are reported but are not separate hard gates.

Otherwise:
`C1_COMPRESSION_T0_INTERACTION_NOT_SUPPORTED`.

## Boundary

A positive result means compression risk modifies the usefulness of the current causal C1 relation.

It does not yet authorize:
- a hard T0 veto threshold;
- a production router;
- live trading.

Any specific operational rule must be separately preregistered.