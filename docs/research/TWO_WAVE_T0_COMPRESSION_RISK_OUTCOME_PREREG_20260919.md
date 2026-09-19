# T0 outcome audit under causal C1 compression-risk bands — preregistration

Issue #515. Parent #507 / #493 / #450.

## Objective

Test whether the already-accepted causal C1 compression risk ranking identifies worse T0 own-lifecycle trade outcomes.

## Frozen inputs

- T0 period-21 breakout own-lifecycle trades;
- walk-forward compression bands B1..B5 from #507, constructed from prior-year feature distributions only.

Frozen zones:
- LOW = B1+B2
- MID = B3
- HIGH = B4+B5
- B5 alone diagnostic.

No score or band threshold may be changed using T0 outcomes.

## Outcome

Use each T0 trade's own `net_log_return_proxy` and existing `fast_loss` flag.

Report by zone:
- N
- mean/median net bp
- win rate
- fast-loss rate
- mean duration
- LONG/SHORT split
- year-by-year mean net bp.

## Bootstrap

Use 20-trading-day calendar blocks of T0 signal bars.

5,000 resamples, seed 20260919.

Primary bootstrap quantities:
- HIGH mean net bp
- HIGH minus LOW mean net bp.

## Gate A — causal risk attenuation

`C1_COMPRESSION_T0_RISK_GATE_SUPPORTED` iff:

1. HIGH mean net bp < LOW mean net bp;
2. bootstrap 95% upper bound for HIGH-LOW mean difference <0;
3. HIGH fast-loss rate > LOW fast-loss rate;
4. HIGH mean net bp < LOW mean net bp in at least 2 of 3 years.

## Gate B — hard veto

`C1_COMPRESSION_T0_HARD_VETO_SUPPORTED` iff Gate A passes and:

1. HIGH mean net bp <0;
2. bootstrap 95% upper bound for HIGH mean net bp <0;
3. HIGH LONG point mean <0;
4. HIGH SHORT point mean <0.

If Gate A passes but Gate B fails, compression is a risk modifier, not a hard veto.

## Boundary

Development evidence only.

No fresh OOS/live/production authority.