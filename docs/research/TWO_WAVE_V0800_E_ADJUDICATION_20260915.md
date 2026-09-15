# Two-Wave v0.8.0 — V0800-E post-audit adjudication

## Decision

The verified V0800-E visual-audit run is `34971340135-1`, profile `two-wave-v0800-e-morphology-visual-audit-v1`, executed from public source SHA `1bb6f89fab8ef34b726f6a77d15a6f3b11b50b31`. Its `AUDIT_MANIFEST.json` SHA256 is `c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5`.

A later transport-only replay exposed the same 59 SVGs to the private run branch and was allowed to succeed only if that manifest digest exactly matched the first verified E run. The digest matched. The visual pack therefore remained the same deterministic sample; no second scientific sample was created.

The post-audit morphology verdict is: **the current Two-Wave morphology definition is semantically coherent enough to nominate one operational parameter pair for the next non-outcome validation gate.** No morphology rewrite is required before that next gate.

The nominated semantic pair is:

- temporal same-level boundary: `rho = sqrt(2)` (already frozen by C2);
- one-wave Range dead-zone: `tau = 0.20`;
- same-direction trend-speed tolerance: `kappa = 2.00`.

This is a semantic nomination, **not** a statistical or performance winner.

## Why `tau = 0.20`

`tau` answers a geometric question: how much can the bottom line migrate, relative to that A-wave's channel height, before the wave should be called directionally meaningful rather than approximately flat?

The deterministic tau-sensitive examples make the boundary visible. In the 2015 audited case `e24-a000252__e24-a000253`, `g_previous=-0.1117` and `g_current=+0.1539`: the two bottom migrations are small and opposite. Calling this directional would exaggerate weak movement; putting both inside a 20%-of-channel-height dead-zone is visually consistent with Range. In the sole 2020 tau-sensitive case `e154-a002409__e154-a002410`, the migrations are `-0.1826` and `-0.0840`; again, both are small compared with channel height and the chart reads as weak drift rather than a robust two-wave decline.

The audit pack contains 21 tau-sensitive pairs in the full eligible universe. The 2020 cell contains only one candidate and the deterministic pack reports that shortage rather than replacing it. Nothing in this adjudication treats the scarcity or the resulting Range count as an optimization objective.

## Why `kappa = 2.00`

`kappa` answers a different geometric question: once two waves point the same way, how different may their normalized bottom-migration magnitudes be before they stop looking like the same trend-speed order?

The audited boundary cases show why `1.25` is too brittle. The 2015 case `e16-a000159__e16-a000160` has `g=0.9989/0.7947`, a slope-magnitude ratio of `1.2569`. The channels are visibly same-direction and same-order, yet `kappa=1.25` rejects them because the ratio is only slightly above the cutoff.

A stronger 2020 boundary case, `e151-a002368__e151-a002369`, has `g=1.9514/1.3005`, ratio `1.5005`. The two waves are still clearly upward, but `kappa=1.50` rejects the pair by a tiny numerical margin while `kappa=2.00` admits it. By contrast, persistent-Uncertain audited examples remain qualitatively different at ratios `2.6759` and `3.4836`; those stay outside a factor-of-two rule. The factor-of-two boundary therefore separates the reviewed “same direction, same speed order” examples from the reviewed “same sign but obviously different speed” examples more faithfully than the narrower cutoffs.

## What the audit did and did not show

The five preregistered categories partition all 924 `rho=sqrt(2)` eligible strict pairs: 49 stable-consensus, 116 kappa-sensitive, 21 tau-sensitive, 406 sign-conflict, and 332 persistent-Uncertain. The deterministic visual pack contains 59 cases, at most two per category-year cell; only `tau_sensitive/2020` has a shortage.

Cross-year reviewed examples behaved according to the intended geometry:

- stable-consensus examples showed two clear same-sign, same-order bottom migrations, including both UpTrend and DownTrend cases;
- kappa-sensitive examples differed mainly in trend-speed consistency rather than direction;
- tau-sensitive examples sat near the intended trend-versus-Range dead-zone;
- sign-conflict examples had visibly opposite bottom-line directions and justified abstention;
- persistent-Uncertain examples were not obvious misses: they were typically same-sign waves with materially different migration speed.

No chart shows any bar after the current A-wave confirmation bar. No future return, PnL, position, cost, or later market context was used for this nomination.

## Authority boundary

This adjudication installs only a **research-operational semantic parameter nomination** for the next validation stage. It does **not** grant direction acceptance, market-state publication authority, trading authority, or production authority.

`(tau=0.20, kappa=2.00)` is not selected because it maximizes decisiveness, minimizes Uncertain labels, balances state counts, or improves any return. Those winner rules remain prohibited. Any later change to `rho`, `tau`, or `kappa` requires a new preregistration; this document is not an automatic tuning license.

## Next gate: V0800-F operational state-stream audit

The next study should freeze `rho=sqrt(2)`, `tau=0.20`, and `kappa=2.00` and examine only the event-time state stream produced at causal confirmation times. Its job is to check persistence, transitions, abstention behavior, and semantic invariants of the sequence itself.

V0800-F must not search parameters, compute future returns or PnL, simulate trades, or use 2026 data. If the fixed state stream exhibits semantic pathologies, the project returns to morphology design. Only if the state-stream audit passes should a later, separately preregistered gate consider any outcome-bearing validation.
