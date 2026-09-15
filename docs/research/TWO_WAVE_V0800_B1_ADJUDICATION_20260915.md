# Two-Wave v0.8.0 B1 adjudication

Status: frozen after verified B1 Development run `34957977925-1`, before V0800-C.

## Verified B1 identity

The accepted B1 run executed profile `two-wave-v0800-b1-strict-continuity-v1` from public source SHA `3c6641fa976159b3528355296f33a8944d124c0f`. The run receipt passed. The input was the already-consumed CSI1000 `5m_offset_0` Development file, 70,114 rows, SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`, restricted to 2015-01-05 through 2020-12-31. No 2026 data was read.

## What B1 established

The frozen v0.4.3 causal pivot kernel produced 2,503 valid A-waves. Of these, 2,358 formed literal shared-anchor strict pairs, so 94.21% of A-waves participate in a consecutive `L-H-L-H-L` relation. Annual strict-pair counts were 368, 476, 407, 334, 401 and 372 for 2015 through 2020.

This is sufficient to keep strict shared-anchor continuity as the only direction-eligible pair semantic for v0.8.0. `same_scale_ledger_nearest` remains diagnostic-only. A skip-based pair still has no direction authority because the current single-scale pivot engine cannot prove that an intervening A-wave is a lower-level nested object.

## What B1 did not establish

B1 did not select a rho. Support among strict pairs rose from 24.89% at rho=1.25 to 45.97% at rho=1.5; legacy rho=2.0 covered 70.36% but remains a non-winning historical control.

The rank association between log duration ratio and normalized 21-point path RMS was -0.0153. The association between log channel-height ratio and path RMS was +0.0338. Fixed duration-ratio bins also did not show a monotone deterioration of normalized path RMS as duration mismatch increased.

This does **not** demonstrate that duration is irrelevant to wave level. The path diagnostic first normalizes time to 21 points and amplitude by each wave's channel height, so it intentionally removes the two scale quantities under examination. Therefore normalized shape similarity is not an admissible empirical selector for rho, and B1 provides no basis for adding a channel-height/amplitude gate.

Duration remains the primary scale coordinate. The candidate rho family remains exactly `{1.25, 4/3, sqrt(2), 1.5}`; rho=2.0 remains legacy control only. No rho winner is installed.

## V0800-C permission

B1 review unblocks **only** V0800-C causal prefix replay. C must carry all four frozen candidate rho values and may not select a winner. It must prove, prefix by prefix, that no future bar can change what was knowable at that prefix for:

- pivot confirmation and append-only pivot identity;
- A-wave availability and confirmation time;
- strict shared-anchor pair availability;
- bottom-authoritative channel geometry;
- same-scale eligibility for every frozen candidate rho.

V0800-C may not introduce direction thresholds, publish Range/UpTrend/DownTrend states, read future outcomes, use PnL or positions, read 2026, or grant trade/production authority.

Only after C passes may a separate preregistered decision determine how the rho family is reduced before any direction grid. B1 itself does not authorize V0800-D.
