# Two-Wave v0.8.0 — V0800-E post-audit adjudication

## Decision

The morphology semantics are accepted for **Layer2 descriptive state publication only** with the following frozen parameters:

- continuity: literal shared-anchor `L-H-L-H-L`;
- knowledge time: current A-wave `confirmation_bar`;
- same-scale boundary: `rho = sqrt(2)` from the previously frozen dyadic half-octave semantic;
- flatness dead-zone: `tau = 0.20`;
- same-direction slope-similarity tolerance: `kappa = 1.50`.

This decision does **not** claim predictive value. No future return, PnL, position, transaction cost, 2026 observation, or later market movement was used to choose `tau` or `kappa`.

## Evidence identity

The scientific visual audit is public research run `34967434004-1`. Its deterministic 59-case manifest has SHA256 `c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5`.

Run `34971340135-1` was a transport replay after the private mirror was extended. It reproduced the exact same manifest byte-for-byte and exposed those same 59 already-selected SVGs privately. It is not a second scientific sample.

Both runs use the already-consumed 2015–2020 Development identity (`70114` bars; parquet SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`).

## Why `tau = 0.20`

`g` is low-to-low log migration normalized by that A-wave's own channel height. `tau=0.20` therefore has a direct geometric reading: a low-to-low displacement no larger than one fifth of the wave's channel height is treated as near-horizontal.

The preregistered tau-sensitive examples showed the intended boundary behavior across 2015–2020. `tau=.05` visibly over-called trend on nearly horizontal channels. `.10` and `.15` corrected progressively flatter cases, but `.15` still left preregistered examples with approximately 15–18% normalized migration as non-Range even though the channel bottoms remained visually shallow relative to their own A-wave heights. `.20` is therefore accepted as the morphology dead-zone. This is a semantic judgment, not a coverage-maximizing rule.

## Why `kappa = 1.50`

`kappa` compares the magnitudes of the two normalized migrations only after both waves already agree on UP or DOWN.

The preregistered kappa-sensitive examples were stable across years. Ratios around `1.26–1.46` still looked like the same directional rhythm, so `1.25` was too strict. By contrast, `kappa=2.0` admitted preregistered examples with normalized-migration ratios around `1.85–1.88`; visually one wave was nearly twice as steep as the other, which contradicts the original requirement that the two waves have **similar slope**. `1.50` is therefore accepted.

## Descriptive state publication rule

For a causally confirmed, literal-consecutive, same-scale pair only:

- `Range`: both `|g| <= 0.20`;
- `UpTrend`: both `g > 0.20` and the magnitude ratio is `<= 1.50`;
- `DownTrend`: both `g < -0.20` and the magnitude ratio is `<= 1.50`;
- `Uncertain`: the eligible pair exists but does not satisfy one of the three rules above.

If there is no literal-consecutive same-scale confirmed pair, this adjudication grants **no directional state publication** for that instant. Skip-based ledger matches remain diagnostic-only.

## Authority boundary

The accepted authority is deliberately narrow: Layer2 may describe current morphology as `Range`, `UpTrend`, `DownTrend`, or `Uncertain` when the eligibility conditions above are met.

This adjudication does **not** authorize:

- a predictive trading signal;
- Layer3 strategy consumption;
- positions, orders, or PnL claims;
- transaction-cost or execution claims;
- production strategy deployment.

The next scientific gate is a separately preregistered **future-information validation of this now-frozen morphology state**. That future study may not reopen `rho`, `tau`, or `kappa` after looking at outcomes, and the consumed 2015–2020 Development evidence must not be described as fresh OOS.
