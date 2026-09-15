# OLS R² D2 execution status

Status at preregistration: **READY_FOR_REVIEWED_EXECUTION**.

The D1 authoritative run `34964393250` supported progression to an exit-overlay A/B. D2 is now frozen as a single deterministic treatment: first two-consecutive-R²-decline warning per original baseline non-flat direction segment, flat from the next executable bar, lockout until that original segment ends.

No parameter search, PE threshold, new entry rule, router, sizing change, leverage change, or production authority is included.

Authoritative D2 claims require:
1. public regression tests,
2. merge to `cloud-workspace-v1`,
3. real standard `workflow_dispatch`,
4. successful isolated compute and independent verifier,
5. successful private publication/readback.

Until those steps complete, this file contains no empirical D2 result.
