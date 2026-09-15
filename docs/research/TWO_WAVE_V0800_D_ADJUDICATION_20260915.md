# Two-Wave v0.8.0 — V0800-D morphology-grid adjudication

## Verified run

The reviewed Development run is `34963875542-1`, profile `two-wave-v0800-d-direction-grid-v1`, public source SHA `a0f7b665ec5c5754ef5d2c21a3bab99f9383a883`.

The standard executor completed prepare → credential-free compute → trusted independent comparison → cleanup → private publish. The input remained the already-consumed CSI1000 `5m_offset_0` Development file from 2015-01-05 through 2020-12-31: 70,114 rows, 3,351,411 bytes, SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`. No substitute data and no 2026 data were read.

## Frozen morphology universe

The strict continuity universe remains `L0-H0-L1-H1-L2`, with the current A-wave usable only at its confirmation bar. There are 2,358 strict pairs in the consumed Development interval. Under the C2 semantic same-level rule `rho=sqrt(2)`, exactly 924 pairs are eligible.

The D grid is the preregistered 4×3 family:

- `tau ∈ {0.05, 0.10, 0.15, 0.20}` controls the one-wave Range dead-zone in normalized bottom migration `g`.
- `kappa ∈ {1.25, 1.50, 2.00}` controls how similar the magnitudes of two same-direction `g` values must be before a trend label is admitted.

One wave never publishes a market state. Only two strict, same-level, causally known waves may form `Range`, `UpTrend`, or `DownTrend`; all other cases remain `Uncertain`.

## What D actually showed

`kappa` is the dominant trend-consistency width knob. For every fixed `tau`, loosening `kappa` from 1.25 to 1.50 to 2.00 raises the decisive fraction from roughly 6–8% to 11–12% to 18.5–19.5%.

`tau` is primarily the Range dead-zone knob. The total Range count across the 924 eligible pairs rises monotonically as `tau` increases: 2 at `tau=0.05`, 6 at `0.10`, 14 at `0.15`, and 23 at `0.20`. Those counts do not depend on `kappa`, as expected from the frozen classifier semantics.

Global UpTrend and DownTrend counts are close to symmetric. Examples at `kappa=2.00` are 86/83 for `tau=0.05`, 83/83 for `0.10`, 81/81 for `0.15`, and 79/78 for `0.20`. This is useful evidence that the rule is not obviously mechanically tilted toward one sign. It is **not** evidence that either sign predicts future returns.

## What D does not authorize

There is no `tau` winner and no `kappa` winner. In particular, `(tau=0.20, kappa=2.00)` must not be promoted merely because it has the largest decisive fraction. That combination is also the widest rule in the frozen grid; maximizing decisiveness would therefore reward permissiveness by construction.

The following are not admissible winner rules at this stage:

- maximum decisive fraction;
- minimum `Uncertain` fraction;
- most balanced state counts;
- any future-return, PnL, position, cost, or trading metric.

D grants no direction acceptance, state-publication authority, trade authority, or production authority.

## Next gate: V0800-E morphology visual audit

The next authorized study is `V0800-E_MORPHOLOGY_VISUAL_AUDIT`. Its job is not to optimize performance. It must inspect deterministic, year-stratified morphology examples at the **confirmation-time information set only** and ask whether the frozen labels match the intended visual geometry.

The audit must include threshold-sensitive and unresolved cases rather than hand-picked successes. At minimum the preregistration should distinguish stable consensus, `kappa`-sensitive, `tau`-sensitive, persistent-Uncertain, and sign-conflict morphology. Sampling must be deterministic from pair identity and year. No bar after the pair's confirmation bar may be shown, and no future return may be computed or displayed.

Only after that morphology-only audit may a separate adjudication decide whether the current `tau/kappa` family is semantically coherent enough to nominate an operational pair. A visual audit success still does not by itself create trading or production authority.
