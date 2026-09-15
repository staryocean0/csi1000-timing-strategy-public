# OLS R² D2 execution status

Status at preregistration: **READY_FOR_REVIEWED_EXECUTION**.

The D1 authoritative run `34964393250` supported progression to an exit-overlay A/B. Its private authority record is fixed at branch `runs/public-research/34964393250-1`, path `research/public-runs/34964393250-1/ols-d1/study/RESULTS.json`, blob `f35ae2ff402c90b54d318b49bd678c5398a60493`.

D2 is frozen as one deterministic treatment: first **same-authority-window** two-consecutive-R²-decline warning per original baseline non-flat direction segment, flat from the next executable bar, lockout until that original segment ends. The same-window guard is part of the treatment because D1 separately established that guard in all 5/5 exit families; D2 must not compare W12 and W24 R² levels across a window switch.

No parameter search, PE threshold, new entry rule, baseline exit mutation, router, sizing change, leverage change, or production authority is included. The preregistered MaxDD/tail/return-retention gates are unchanged from the first D2 draft; no D2 outcome has been opened before this clarification.

Authoritative D2 claims require:
1. public regression tests,
2. merge to `cloud-workspace-v1`,
3. real standard `workflow_dispatch`,
4. successful isolated compute and independent verifier,
5. successful private publication/readback.

Until those steps complete, this file contains no empirical D2 result.
