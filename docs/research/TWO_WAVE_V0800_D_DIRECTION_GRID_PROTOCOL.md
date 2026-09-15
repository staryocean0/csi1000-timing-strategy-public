# Two-Wave v0.8.0 — V0800-D direction grid protocol

Status: preregistered before any V0800-D real-data execution.

## Scope

V0800-D is the first experiment in the reboot that is allowed to ask whether **two consecutive same-level A-waves describe a common direction**. It is still a Layer2 morphology diagnostic, not a trading strategy.

All upstream gates are fixed:

- causal timing is the V0800-C confirmation-time ledger;
- only literal shared-anchor `L-H-L-H-L` pairs are eligible;
- same temporal level is the C2 dyadic rule `rho=sqrt(2)`;
- skip-based predecessor pairs are excluded;
- legacy rho=2 is not evaluated.

The data remain the already-consumed CSI1000 5m Development interval 2015-01-05 through 2020-12-31. No 2026 data are opened.

## One-wave coordinate

For an A-wave `L0-H0-L1`, the bottom-authoritative channel is already frozen. Define

`g = (log(L1)-log(L0)) / channel_height_log`.

`g` measures how far the authoritative bottom anchor migrated between the two lows relative to that wave's own channel height.

For a frozen threshold `tau`:

- `abs(g) <= tau` -> internal descriptor `Range`;
- `g > tau` -> internal descriptor `Up`;
- `g < -tau` -> internal descriptor `Down`.

This descriptor belongs to one wave only. **One wave never publishes a market state.**

## Two-wave rule

Let `g_prev` and `g_cur` be the normalized migrations of the two strict consecutive same-scale waves.

For each frozen `(tau,kappa)` combination:

- both descriptors `Range` -> pair state `Range`;
- both descriptors `Up`, and
  `max(|g_prev|,|g_cur|)/min(|g_prev|,|g_cur|) <= kappa`
  -> `UpTrend`;
- both descriptors `Down` with the same slope-magnitude consistency condition -> `DownTrend`;
- everything else -> `Uncertain`.

The state becomes knowable only at the current A-wave's confirmation bar.

## Frozen grid

Tau candidates remain exactly:

`{0.05, 0.10, 0.15, 0.20}`.

Kappa candidates remain exactly:

`{1.25, 1.50, 2.00}`.

This produces 12 morphology-only parameter combinations. No extra tau/kappa value may be introduced after seeing D results.

## First D output

The row-level ledger contains one row for every eligible strict same-scale pair and every frozen `(tau,kappa)` combination. It records only morphology quantities and the resulting pair state.

For each combination the aggregate summary reports:

- eligible pair count;
- counts of `Range`, `UpTrend`, `DownTrend`, `Uncertain`;
- decisive fraction `(Range + UpTrend + DownTrend) / eligible`;
- annual state counts for 2015 through 2020.

These are morphology diagnostics only.

## No automatic winner

V0800-D must **not** select tau/kappa simply because a combination:

- maximizes decisive coverage;
- minimizes `Uncertain`;
- produces aesthetically balanced state shares;
- would later improve returns or PnL.

The first real D run installs no tau winner and no kappa winner. A separate post-run adjudication must decide whether the direction semantics are coherent and how any parameter reduction is justified.

## Forbidden evidence and authority

V0800-D does not read future outcomes or returns, does not calculate PnL, positions, transaction costs or execution signals, and does not open 2026.

A successful D run does not by itself grant direction publication authority, trade authority or production authority.
