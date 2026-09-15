# Layer3 OLS family migration

Status: cloud research migration package; not production authority.

This package reclassifies the OLS trend-regime lineage from its historical Layer2 research placement into the cloud Layer3 research namespace. It does not rewrite history and it does not decide how the fuller local Layer3 inventory will eventually absorb this package.

## Boundary

The migration boundary is intentionally lineage-based:

- KEEP IN HISTORICAL LAYER2 / TWO-WAVE: the earlier K-line recognizer / true-wave / two-wave line. Commit `d30400e52a65888192bdb62e86f493eb81cbd8e2` records that `kline-recognizer` v1-v13 was moved to `staryocean0/factorlab-two-wave-strategy-lab`; that material is not copied here.
- MIGRATE TO LAYER3: the trend-regime component line restarted on 2026-09-14 after parent `ab4979b224d8ee97f89b75ac428ddd71887fecf1`, beginning with roadmap commit `8a2d599f5734dbdf612655b7f027136f2507f7fa`, with OLS baseline frozen at commit `cb280fa3b5137dea34ccaa1c0c9f33af821a52fa`.
- SOURCE SNAPSHOT: `staryocean0/factorlab-trend-reversion-regime-lab@69e83973f6213d308a4b3afc6b3715b76e3d67b7`.

The fixed comparison `ab4979b224d8ee97f89b75ac428ddd71887fecf1..69e83973f6213d308a4b3afc6b3715b76e3d67b7` contains 353 descendant commits. That range is the provenance envelope for the OLS family. External experiment results remain external evidence until the CSI1000 public/private control plane imports/replays and accepts them.

## Physically migrated reusable components

The current external main adds four reusable trend-regime runtime modules after the OLS pivot; verbatim source snapshots are stored in `source_snapshot/`:

1. `trend_regime_baseline.py` — M2, 20 completed bars, `log(close)`, time-index OLS, signed slope t-score, `T1=2` three-bucket state.
2. `trend_regime_profiles.py` — M3, binds the frozen OLS measurement to admitted 1m/5m/15m/60m Layer1 views.
3. `trend_regime_representation.py` — M6, three categorical states plus continuous `abs(slope_t)` strength.
4. `trend_regime_consumer.py` — M7, immutable snapshot/query consumer contract.

These are source snapshots for migration and review, not wired executor modules. In particular, the historical source still imports its original `factor_lab` Layer1 dependencies. Native CSI1000 wiring is deliberately deferred to the later local Layer3 merge/integration task.

## OLS descendants included in Layer3 scope

The migration scope includes the component/governance sequence M2–M9 and the post-V1 research descendants that remain tied to the OLS strength/state primitive: cross-profile invariance, distribution/state-dynamics checks, five-carrier replication, source robustness, 15m/60m cross-carrier work, interval calibration, temporal-scale normalization, strength-scale decomposition, dynamic/adaptive scale work, prospective fast-vs-adaptive comparison, turnover regularization, sparse hysteresis, partial-reset/cooldown, anchored structural validation, structural-failure attribution, and causal regime-observable identifiability (X2 through X5O as recorded in the source repository).

`MIGRATION_MANIFEST.json` freezes that boundary. The migration does not import unrelated pre-pivot R1/R2 reversal/option research and does not move the Two-Wave lineage.

## Authority

This public package establishes cloud-side Layer3 placement and provenance only. It does not grant production authority, does not make the external factorlab repository current authority for CSI1000, and does not claim external historical experiment receipts as accepted CSI1000 scientific results.
