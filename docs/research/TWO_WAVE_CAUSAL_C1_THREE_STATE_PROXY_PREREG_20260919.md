# Causal C1 three-state proxy — preregistration

Issue #533. Parent #531 / #507 / #480 / #450.

## Objective

Test whether a fully causal three-state proxy can reproduce the retrospective C1 gate structure observed in #480.

## Frozen universe

Use exact #507 strict-v2 2018–2020 T0 scored signal bars and frozen period-21 own-lifecycle T0 trades.

## Causal proxy

At T0 signal bar k:
- compute ret8 = log(close[k]/close[k-8]);
- if risk_band == B5: C1_PROXY = UNRESOLVED;
- else if sign(ret8) equals T0 trade side: C1_PROXY = ALIGNED;
- else: C1_PROXY = OPPOSED.

No other band, threshold, lookback or feature is used.

## Outcome

Use frozen T0 own-lifecycle net_log_return_proxy and existing fast_loss flag.

Report for ALIGNED / OPPOSED / UNRESOLVED:
- N
- mean/median net bp
- win rate
- fast-loss rate
- mean duration
- LONG/SHORT split
- year-by-year mean net bp.

## Bootstrap

20-trading-day calendar blocks, 5,000 resamples, seed 20260919.

Report 95% CI for:
- ALIGNED mean net bp
- OPPOSED mean net bp
- ALIGNED minus OPPOSED mean net bp.

## Gate

CAUSAL_C1_THREE_STATE_PROXY_SUPPORTED iff all are true:

1. ALIGNED pooled mean net bp >0;
2. bootstrap 95% lower bound for ALIGNED mean net bp >0;
3. OPPOSED pooled mean net bp <0;
4. bootstrap 95% upper bound for OPPOSED mean net bp <0;
5. bootstrap 95% lower bound for ALIGNED-OPPOSED mean net difference >0;
6. ALIGNED yearly mean >0 in at least 2 of 3 years;
7. OPPOSED yearly mean <0 in at least 2 of 3 years.

UNRESOLVED is descriptive only.

## Boundary

This candidate was discovered on consumed development evidence after #531 and therefore requires independent validation even if it passes.