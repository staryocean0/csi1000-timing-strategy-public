# High-compression T0 early-progress confirmation exit — preregistration

Issue #527. Parent #525 / #523 / #507 / #450.

## Objective

Test whether HIGH-compression T0 trades benefit from an early progress check rather than a pre-entry veto.

## Frozen universe

Use exact #507 strict-v2 scored 2018–2020 T0 signals.

Only HIGH compression trades are modified:
- HIGH = B4+B5.

LOW/MID are unchanged and are not used for parameter selection.

## Frozen T0 execution

Period-21 own-lifecycle breakout, next-open fill, 2bp/side proxy cost.

## Candidate overlays

H4:
- if original T0 exit occurs on/before entry+4: keep original exit;
- otherwise evaluate signed gross MTM at raw open entry+4;
- if MTM <=0: exit at entry+4;
- if MTM >0: keep original T0 exit.

H8:
- same rule at entry+8.

Both horizons are preregistered. No other horizon or MTM threshold is searched.

Any early-exited completed trade still pays total 4bp proxy round-trip cost.

## Outputs for each horizon

- N HIGH trades
- early-exit count/rate
- original mean/median/q10 net bp
- modified mean/median/q10 net bp
- paired modified-minus-original mean net bp
- paired q10 difference
- modified win rate
- modified mean duration
- fraction of early-exited trades that would have been final winners under original T0
- yearly paired mean difference.

## Bootstrap

20-trading-day calendar blocks of HIGH T0 signal bars.

5,000 resamples, seed 20260919.

Report 95% CI for:
- paired mean-net difference
- q10-net difference.

## Candidate acceptance

A horizon is marked EARLY_PROGRESS_CANDIDATE_SUPPORTED iff all are true:

1. paired mean-net difference >0;
2. bootstrap 95% lower bound for mean-net difference >0;
3. modified q10 > original q10;
4. bootstrap 95% lower bound for q10 difference >0;
5. yearly paired mean difference >0 in at least 2 of 3 test years;
6. among early-exited trades, original-T0 final winner fraction <=30%.

If neither H4 nor H8 passes, early-progress confirmation is rejected.

If both pass, both remain candidates; this study does not choose between them.

## Boundary

Consumed development evidence only. A supported candidate requires independent validation.