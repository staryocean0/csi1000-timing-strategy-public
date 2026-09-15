# Legacy OLS external-evidence closeout

Status: immutable external-evidence packet for the CSI1000 Layer3 OLS family. This is not a new research result and does not grant production authority.

## Why this packet exists

The historical repository `staryocean0/factorlab-trend-reversion-regime-lab` continued to receive OLS trend-regime work after the CSI1000 public/private pair had become the only valid project control plane. The CSI1000 public repository already corrected the placement problem on 2026-09-15 by importing the OLS lineage from the historical repository at immutable snapshot `69e83973f6213d308a4b3afc6b3715b76e3d67b7`, and the reviewed package was subsequently synchronized into the private repository.

This packet adds one final closeout safeguard before the legacy repository is retired: it copies the small, decision-bearing X5M/X5N/X5O records that explain the last meaningful representation research, rather than retaining only milestone names in a lineage manifest.

## Audit result

The observed legacy head is `69e83973f6213d308a4b3afc6b3715b76e3d67b7`. The existing CSI1000 migration commit `f68979008dd7b201be8328d8e8000c146eadf372` was created after that legacy head and explicitly freezes the same source snapshot, including X5M, X5N and X5O in its descendant scope. The CSI1000 pair then continued into the OLS drawdown-control D0 stage, so current project progress is downstream of the legacy snapshot.

Accordingly, there is no newer legacy OLS commit to rescue. What remains worth preserving is the final evidence boundary:

- X5M: the anchored-partial normalized-strength candidate did not generalize across fixed structural blocks; no post-result retuning was allowed.
- X5N: normalization failure was regime-conditional, with a specific 000016 interaction, but neither carrier composition nor median-vs-mean common scaling explained the main failure.
- X5O: preregistered slope-independent causal return-geometry observables did not identify the failure regimes strongly enough to authorize a regime switch. `CORRELATION_BREAK` remained a diagnostic clue only.
- Final representation consequence: `NO_CHANGE`; X6 remains `HOLD_NOT_READY`; unified dynamic `normalized_strength` development must not be rescued by retuning on these outcomes.

## Authority boundary

These files are preserved as external evidence with exact source repository, source commit and source blob identities in `EVIDENCE_MANIFEST.json`. They do not become accepted CSI1000 scientific results merely by being copied. Any later reuse must respect the CSI1000 public/private control plane, consumed-data semantics and preregistration rules.

The legacy repository must not regain `current authority`, `active_research`, project-level workflow state or a canonical BLACKBOX ledger after this closeout.
