# Two-Wave trade-oriented taxonomy V2 — low-amplitude actionability sub-freeze

Issue #411. Parent direction freeze: #409 / merge `c3587379457b2c67ae57c473a811ab819c5c0134`.

## 1. Purpose

This document freezes the numeric LOW_AMPLITUDE_VETO used by the new five-state current-band-first taxonomy.

The goal is intentionally narrow:

> If the total locally observable price excursion is so small that even perfect endpoint capture cannot cover a current project-level round-trip cost proxy, stop structural interpretation and classify LOW_AMPLITUDE_VETO.

This is a hard lower-bound veto. Passing the veto does **not** imply that a trade is profitable or executable.

## 2. Current project cost reference

Private project reference, read-only:

- `runtime/docs/ops/timing_asset_cost_boundary_registry@2.0.json`
- blob SHA: `9afe1102fb4debad6c5b8ddf5669054371284ec9`
- schema: `factorlab.timing_asset_cost_boundary.registry.v2`
- `current = true`

The selected signal-level proxy is:

- contract: `market_index_equity_replication_1bp_6bp_sensitivity@1.0`
- entry rate: 1bp
- exit rate: 6bp
- complete round-trip rate: **7bp**
- tradable_account: false

The proxy is selected because it gives a simple, current, project-level lower bound in index-return units. It is not represented as a live account or production cost model.

## 3. Why not use the MO option fee directly

The same current cost registry also includes:

- MO long option: ask entry / bid exit / CNY 14 per contract per side;
- MO short option: bid entry / ask exit / CNY 14 per contract per side.

But a fixed index-bp break-even cannot be derived from the CNY 14 fee alone. MO economics also depend on contract premium, bid/ask spread, delta/forward mapping, moneyness, DTE and liquidity.

The project already has an identified option lifecycle cost map:

`csi1000_option_lifecycle_cost_map@1.0`

with dynamic delta-equivalent spread+fee treatment. Therefore V2 does not compress MO into a fake constant index-bp threshold.

The 7bp proxy is only a **signal-layer hard floor**.

## 4. Fixed information window

For target native 5m bar `t`, the taxonomy is allowed evidence through `t+8`.

The low-amplitude window is fixed as:

`[t-8, t+8]`

inclusive, therefore 17 native 5m bars.

Rationale:

- it is centered on the target;
- it uses exactly the already authorized eight-bar confirmation tail;
- it includes at least the historical minimum complete-wave span (~8 bars) on the pre-target side;
- it avoids letting a distant 64/128/256-bar move rescue a locally tiny target region.

If the complete 17-bar window is not available, this is an evidence-edge condition and must not be silently imputed.

## 5. Frozen amplitude metric

Use native OHLC high/low, not only close.

For the 17-bar window, define:

[
A_{local,bps}
=
10000 	imes
left(
max_i log(H_i)
-
min_i log(L_i)
ight)
]

for all bars `i in [t-8,t+8]`.

This is the maximum observable geometric excursion in the local evidence window.

It intentionally uses the full high-low range because the veto asks an impossibility question:

> Is even the maximum imaginable endpoint capture too small?

A separate DATA_INVALID gate must run first, so a genuine data spike/outlier is not allowed to turn an invalid panel into an actionable one.

## 6. Frozen threshold

[
A_{min}=7	ext{ bp}
]

Decision:

- if `A_local_bps < 7`: `LOW_AMPLITUDE_VETO`;
- if `A_local_bps >= 7`: amplitude veto passes and classification continues.

Equality passes to the structural classifier. The veto therefore remains a strict impossibility lower bound.

## 7. Interpretation

A panel above 7bp is **not** declared profitable.

It only means:

> the maximum local excursion is not already smaller than the current 7bp project-level round-trip signal proxy.

Actual tradability may require a much larger move after spread, slippage, imperfect capture, contract mapping and market impact.

Those later questions belong to Layer4/economic validation, not to this taxonomy label.

## 8. Diagnostic sensitivities

The following may be reported after the primary labels are frozen:

- 14bp;
- 21bp.

They are diagnostic sensitivity levels only.

They may not be used to relabel the primary V2 reference set after seeing category counts, recognizer accuracy, future returns or PnL.

## 9. Order relative to other states

The five-state precedence is now concretely:

1. unusable/invalid evidence -> DATA_INVALID;
2. `A_local_bps < 7` -> LOW_AMPLITUDE_VETO;
3. otherwise test current-band structure;
4. valid current-band structure -> CURRENT_UP / CURRENT_RANGE / CURRENT_DOWN;
5. only if current-band structure is absent, test repeated sub-4-bar oscillation -> FINER_SCALE_OUT_OF_BAND;
6. unresolved mechanism during reference construction -> RESEARCH_UNRESOLVED.

No parent-scale or multiscale-context label may override a valid current-band result.

## 10. No economic authority

This sub-freeze grants no strategy selection, routing, paper/live, PnL-selection or production authority.

It only freezes the minimum amplitude veto for rebuilding the V2 reference taxonomy.
