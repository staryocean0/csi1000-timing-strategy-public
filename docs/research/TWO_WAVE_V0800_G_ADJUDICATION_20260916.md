# Two-Wave v0.8.0 — V0800-G bar-time carrier adjudication

## Decision

The verified V0800-G run is `35043795953-1`, profile `two-wave-v0800-g-bar-time-carrier-semantics-v1`, executed by the standard `public-compute.yml` workflow from public source SHA `afd9de82f514dc101d273c685fa541ff847ed5ff` on `cloud-workspace-v1` as a real `workflow_dispatch` run.

Prepare, compute, independent verification, cleanup, private archive writeback, and aggregate private mirror all passed. The private receipt reports `archive_uploaded_and_verified`.

The post-run adjudication is:

**Accept `current_first_until_next_strict_or_reset` as the fixed bar-time carrier semantics for subsequent research. Reject `hold_until_next_eligible` as an authority candidate. Do not add a fixed expiry and do not retune morphology or expiry parameters from this run.**

This is a carrier-semantics acceptance only. `direction_acceptance`, `state_publication_authority`, `trade_authority`, and `production_authority` remain false.

## Input identity

The run consumed exactly the already-used Development carrier:

- symbol `000852.SH`;
- timeframe `5m_offset_0`;
- rows `70114`;
- bytes `3351411`;
- SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`;
- source ref `152ae1ef11a04bb3b434da25025794db7a706c81`;
- interval `2015-01-05 .. 2020-12-31`;
- substitute data false;
- 2026 read false.

No future returns, PnL, positions, transaction costs, trade simulation, or parameter search were used.

## Primary carrier result

The frozen event universe remained exactly `2358` strict events, `924` same-scale eligible events, and `164` resets. The morphology parameters remain `rho=sqrt(2)`, `tau=0.20`, and `kappa=2.00`.

There were `180` decisive events (`Range`, `UpTrend`, or `DownTrend`), and all `180` created at least one carrier bar. The first carrier bar was always `confirmation_bar + 1`, so the minimum carrier lag was exactly one bar. There were no zero-length decisive intervals and no terminal right-censored interval in this consumed sample.

The primary current-first carrier occupied `4403 / 70114 = 6.28%` of bars:

- `DownTrend`: `2024` bars from `79` intervals;
- `Range`: `474` bars from `23` intervals;
- `UpTrend`: `1905` bars from `78` intervals.

The maximum observed carrier age was `59` bars. This is a measured natural tail under strict-event/reset invalidation, not a newly selected expiry cap.

## Every newer strict event remains authoritative evidence

The primary stream ended active carriers through the frozen current-first rules:

- decisive supersession with active carrier: `20`;
- `Uncertain` clear with active carrier: `64`;
- `NoStateScaleMismatch` clear with active carrier: `88`;
- reset clear with active carrier: `8`.

This validates the intended semantics: a previously decisive label is not allowed to survive newer strict morphology evidence merely because that newer evidence is ineligible or uncertain.

## Eligible-only holding is materially stale

The diagnostic `hold_until_next_eligible` anti-control occupied `9785` bars, versus `4403` bars for the primary carrier. It therefore created `5382` stale-or-extra carried bars.

It ignored `222` scale-mismatch events while a carrier was active. Those stale/extra bars formed `88` episodes with:

- median length `48` bars;
- p75 `79` bars;
- p90 about `144.9` bars;
- p99 about `250.3` bars;
- maximum `259` bars.

This is a large semantic distortion relative to the current-first rule. The anti-control is therefore rejected as an authority candidate. Scale mismatch is newer strict evidence and must continue to clear the previous carrier beginning on the following bar.

## No fixed expiry is added

G found a finite natural maximum age of `59` bars under the preregistered current-first rule, with no terminal right-censor in this sample. That observation does not justify selecting `59`, or any other number, as a fixed expiry.

A fixed expiry search was explicitly forbidden in G. Carrier coverage of `6.28%` is also not an optimization target. G does not authorize changing `rho`, `tau`, `kappa`, adding a fixed bar cap, or weakening strict-event invalidation merely to increase coverage or persistence.

## What G supports

G supports the following narrow statement:

> A causally confirmed decisive Two-Wave morphology event may be carried onto the bar timeline beginning at the next bar open, and that carrier must be replaced or cleared after every later strict event or reset according to the frozen current-first rules.

This closes the timing ambiguity left open by F. The carrier is now well-defined as a research coordinate.

## What G does not support

G does **not** show that:

- `UpTrend` predicts a positive future return;
- `DownTrend` predicts a negative future return;
- `Range` predicts profitable or stable future behavior;
- low carrier coverage should be rescued by parameter tuning;
- the morphology labels are ready for a published market-state feed;
- the carrier should drive positions or strategy routing;
- the carrier has trading or production authority.

The run used consumed Development data only. Nothing in G converts it into fresh out-of-sample evidence.

## Authority boundary

This adjudication grants only **bar-time carrier semantic coherence for research**.

It preserves:

- `direction_acceptance = false`;
- `state_publication_authority = false`;
- `trade_authority = false`;
- `production_authority = false`;
- `parameter_search_used = false`;
- `year_2026_read = false`.

No outcome-bearing gate is automatically opened by this document. Any later outcome or publication study must be separately preregistered against this accepted current-first carrier definition, and must keep the distinction between consumed Development evidence and genuinely fresh evidence explicit.
