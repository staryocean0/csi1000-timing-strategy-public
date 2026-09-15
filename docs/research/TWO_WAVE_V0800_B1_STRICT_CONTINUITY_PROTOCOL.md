# Two-Wave v0.8.0 — B1 Strict-Continuity Adjudication

Status: preregistered Development diagnostic. Not private authority. No direction, trade, or production authority.

## Why B1 exists

The verified post-Amendment-A V0800-B run (`34951777247-1`) showed that duration-scale matching has broad support, but tightening `rho` did not materially lower the median normalized path distance. It also showed a large gap between two notions that the parent protocol intentionally kept separate:

- `shared_anchor_strict`: literal consecutive `L-H-L-H-L`, where the previous A-wave ends at the current A-wave's starting low;
- `same_scale_ledger_nearest`: search backward past out-of-scale A-waves until the nearest same-scale A-wave is found.

The user's semantic is **two consecutive waves**. The current v0.4.3-derived pivot stream is single-scale and does not mark an intervening A-wave as a nested lower-level object. Therefore B1 fails closed: skip-based pairs remain useful diagnostics, but they cannot be treated as direction-eligible consecutive pairs unless a later hierarchical scale model explicitly proves the intervening object is lower-scale structure.

## Object under test

B1 uses only strict shared-anchor A-wave pairs:

`L0-H0-L1-H1-L2`

with

- previous wave `W_prev=(L0,H0,L1)`;
- current wave `W_cur=(L1,H1,L2)`.

Both waves come from the unchanged v0.4.3 causal confirmation kernel (`min_leg=4`, `max_unfinished_leg=48`). No new pivot finder is introduced.

Duration remains

`d(W)=end_low_occurrence_bar-start_low_occurrence_bar`

measured in **bar intervals**. Inclusive observed rows equal `d+1`; that derived count is never used for matching.

## Questions

B1 does not choose a `rho`. It asks:

1. Among literal consecutive pairs, how often do the existing frozen rho gates regard the two waves as same-scale?
2. Does smaller duration mismatch actually correspond to smaller normalized path distance?
3. When a strict pair fails a narrow duration gate, is its path shape materially worse than pairs that pass?
4. Is amplitude mismatch more strongly associated with path mismatch than duration mismatch?
5. Are these structural relations broadly present across 2015–2020, rather than driven by one year?

The four v0.8 candidate rhos remain exactly `1.25`, `4/3`, `sqrt(2)`, and `1.5`. Historical `rho=2.0` is a non-winning width control only.

## Frozen measurements

For each strict pair, record:

- duration ratio `max(d_prev,d_cur)/min(d_prev,d_cur)`;
- channel-height ratio, diagnostic only;
- the same 21-point bottom-channel-normalized path RMS used in V0800-B;
- confirmation year and strict shared anchor identity.

Report two rank associations across valid strict pairs:

- Spearman correlation of `log(duration_ratio)` with path RMS;
- Spearman correlation of `log(channel_height_ratio)` with path RMS.

Also report fixed duration-ratio bins: `[1,1.25]`, `(1.25,4/3]`, `(4/3,sqrt(2)]`, `(sqrt(2),1.5]`, `(1.5,2]`, and `>2`.

These are descriptive diagnostics. No correlation, bin, or rho may become a winner from B1.

## Fail-closed boundary

B1 reads only the already-consumed 2015-01-05 through 2020-12-31 `5m_offset_0` Development file with frozen identity SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`.

No 2026 data, future returns, PnL, positions, transaction costs, routing, or trading labels are permitted. `rho_winner` remains null; `morphology_acceptance`, direction authority, trade authority, and production authority remain false.

V0800-C is blocked until this strict-continuity ambiguity is reviewed.

## Runner wiring state

The B1 profile is registered only in the standard `public-compute.yml` workflow and exact-title bounded controller. The branch has been reconciled with the latest public base so concurrent Risk Tool consumer-contract routing is preserved. No B1 real-data run is considered valid until merge-state CI is green on that reconciled head and the PR is merged.
