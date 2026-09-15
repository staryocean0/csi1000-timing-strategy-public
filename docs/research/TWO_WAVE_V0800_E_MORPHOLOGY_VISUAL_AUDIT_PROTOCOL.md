# Two-Wave v0.8.0 — V0800-E morphology visual audit protocol

## Purpose

V0800-E is a morphology-only semantic audit. It does **not** choose the parameter pair with the highest coverage, the fewest `Uncertain` labels, the best state balance, or the best future return. Its only question is whether the labels produced by the frozen D grid look geometrically faithful to the intended concepts when viewed with exactly the information available at the current A-wave confirmation time.

The upstream semantics are frozen: strict shared-anchor `L0-H0-L1-H1-L2` pairs, causal confirmation-time knowledge, operational temporal-level boundary `rho=sqrt(2)`, bottom-authoritative A-wave channels, taus `{0.05,0.10,0.15,0.20}`, and kappas `{1.25,1.50,2.00}`.

## Five mutually exclusive audit categories

Cases are assigned in this priority order so the visual pack is not built by hand-picking attractive examples.

1. **stable_consensus** — all 12 grid states are identical and the common state is not `Uncertain`.
2. **kappa_sensitive** — at fixed `tau=0.10`, `kappa=1.25` is `Uncertain` while `kappa=2.00` is `UpTrend` or `DownTrend`.
3. **tau_sensitive** — after excluding the prior categories, at fixed `kappa=1.50` the states at `tau=0.05` and `tau=0.20` differ.
4. **sign_conflict** — after excluding prior categories, at `tau=0.10` the two one-wave descriptors have opposite signs (`UP` versus `DOWN`).
5. **persistent_uncertain** — after excluding prior categories, all 12 states are `Uncertain`.

These definitions are morphology-only. No future outcome enters category assignment.

## Deterministic year-stratified sampling

For each category and each year 2015–2020, select at most two cases. The ranking key is:

`sha256("V0800-E-v1|" + category + "|" + year + "|" + pair_id)`

and the smallest hashes win. If a category-year cell contains fewer than two cases, take all available cases and report the shortage. There is no replacement from another year or category. The maximum pack is therefore 60 cases.

This rule is frozen before any E result is observed. Cherry-picking is prohibited.

## What a visual case may show

The chart starts exactly at the previous A-wave's first low and ends exactly at the current A-wave's **confirmation bar**, inclusive. It may show native high-low ranges and close markers, the five pivots, the confirmation marker, both bottom-authoritative channel lines and their exact parallel tops, the two durations, duration ratio, `g_previous`, `g_current`, slope-magnitude ratio, and the full 4×3 state matrix.

The confirmation delay segment from terminal `L2` to the confirmation bar is allowed because it is part of the information required to know that `L2` exists. **No bar after the confirmation bar may be displayed.** No future return, PnL, position, transaction cost, or later market context may appear anywhere in the pack.

SVG output must expose one explicit `bar` group per plotted bar with its source bar index. The independent verifier must require those indices to equal the complete integer interval from `previous_start_bar` through `confirmation_bar`, with no missing or extra bar and no index after confirmation.

## Human audit questions

The pack is intended to answer five bounded questions: whether stable labels look visually stable; whether kappa-sensitive cases really differ mainly in slope-magnitude consistency; whether tau-sensitive cases look like a plausible trend/range boundary; whether persistent-Uncertain cases are genuinely ambiguous rather than obvious misses; and whether sign-conflict cases visually justify abstention.

The visual reviewer is not allowed to inspect what happened after confirmation, and is not allowed to infer a preferred threshold from returns.

## Authority boundary

A successful E run only means that a deterministic, causally bounded visual pack was produced and independently verified. It does not install a `tau` winner or a `kappa` winner. It does not grant direction acceptance, state-publication authority, trade authority, or production authority.

After the pack is reviewed, a separate post-audit adjudication may decide whether the current grid is semantically coherent enough to nominate an operational parameter pair or whether the morphology definition must be revised first.
