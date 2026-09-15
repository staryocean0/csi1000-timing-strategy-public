# Two-Wave v0.8.0 — V0800-C adjudication

Status: frozen after verified real Development run `34961575435-1` and before any rho reduction or direction research.

## What C proved

V0800-C replayed all 70,114 bars of the already-consumed CSI1000 `5m_offset_0` Development file (2015-01-05 through 2020-12-31, SHA256 `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`). The standard public executor completed successfully, including credential-free compute, the independent trusted-output comparison, cleanup, verified private publication, and the bounded aggregate mirror.

The independent incremental producer completed the replay with append-only event ledgers whose visibility is `confirmation_bar_only`. It produced 5,471 pivots, 164 resets, 2,503 A-waves and 2,358 strict shared-anchor pairs. The earliest emitted event was at confirmation bar 4 and the latest at bar 70,090. The maximum observed pivot confirmation delay was 41 bars.

This closes the causal-prefix gate: the v0.4.3 timing semantics can be reproduced in an online incremental implementation without treating future-confirmed pivots or waves as already known.

The 41-bar maximum confirmation delay is operationally important. A pivot occurrence time is not a knowledge time. Any future Layer2 direction descriptor must be evaluated from the confirmation-time ledger, never retrospectively from the pivot occurrence bar.

## What C did not prove

C was not a rho-selection experiment. The four frozen candidate values remained `{1.25, 4/3, sqrt(2), 1.5}` and the legacy rho=2 control was not evaluated in C.

The same-scale strict-pair counts were 587, 772, 924 and 1,084 respectively. These exactly reproduce the already-known B1 support counts under the causal replay. That is evidence that the support calculation is point-in-time reproducible; it is not new evidence that one candidate rho is superior to another.

Therefore:

- `rho_winner = null` remains unchanged;
- no duration bound is promoted from candidate to authority by C;
- no tau or kappa direction threshold is opened;
- no Range/UpTrend/DownTrend state may be published;
- no outcome, return, PnL, position, 2026, trade or production authority is introduced.

## Next gate

The next research gate is **V0800-C2 rho semantic adjudication**. Its job is not to search for a profitable rho. Its job is to state, before any direction grid, a principled operational meaning of “same temporal level” and either reduce the four frozen candidate ratios or define a deterministic rule for carrying them forward.

C2 may not use future returns, PnL or 2026 and may not tune tau/kappa. V0800-D remains explicitly blocked until C2 is preregistered and adjudicated.
